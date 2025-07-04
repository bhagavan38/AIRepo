import streamlit as st
import boto3
import json
import base64
import requests
import io
from PIL import Image
import os
import tempfile
from dotenv import load_dotenv
import PyPDF2
load_dotenv()

# Configure page
st.set_page_config(
    page_title="AWS Services Integration",
    page_icon="🚀",
    layout="wide"
)

# Initialize AWS clients
@st.cache_resource
def get_aws_clients():
    try:
        bedrock = boto3.client(
            'bedrock-runtime', region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        lambda_client = boto3.client('lambda', region_name=os.getenv('AWS_REGION', 'us-east-1'))
        lex_client = boto3.client(
            'lexv2-runtime',region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        return bedrock, lambda_client, lex_client
    except Exception as e:
        st.error(f"Error initializing AWS clients: {str(e)}")
        return None, None, None

# Audio recording utility
def record_audio(duration=5, samplerate=16000):
    st.info(f"Recording for {duration} seconds...")
    recording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
    sf.write(temp_file.name, recording, samplerate)
    return temp_file.name

def generate_text(prompt, bedrock_client):
    try:
        response = bedrock_client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 500,
                "temperature": 0.7
            })
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as e:
        return f"Error generating text: {str(e)}"

def generate_image(prompt, bedrock_client):
    try:
        response = bedrock_client.invoke_model(
            modelId="stability.stable-diffusion-xl-v1",
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "text_prompts": [{"text": prompt}],
                "cfg_scale": 10,
                "seed": 42,
                "steps": 50
            })
        )
        result = json.loads(response['body'].read())
        image_data = base64.b64decode(result['artifacts'][0]['base64'])
        image = Image.open(io.BytesIO(image_data))
        return image
    except Exception as e:
        return f"Error generating image: {str(e)}"

def call_lambda_summarize(text, lambda_client):
    try:
        payload = {"body": json.dumps({"text": text})}
        response = lambda_client.invoke(
            FunctionName='summarize_lambda',
            InvocationType='RequestResponse',
            Payload=json.dumps(payload),
        )
        response_payload = json.load(response['Payload'])
        return json.loads(response_payload['body']).get("summary", "No summary returned")
    except Exception as e:
        return f"Error calling Lambda: {str(e)}"

def call_api_gateway_translate(text, direction):
    try:
        url = "https://27ct2aina3.execute-api.us-west-2.amazonaws.com/stage/translation"
        payload = {"body": json.dumps({"text": text, "direction": direction})}
        response = requests.post(url, json=payload, headers={"Content-Type": "application/json"})
        if response.status_code == 200:
            inner_body = json.loads(json.loads(response.text)["body"])
            return inner_body.get("translation", "Translation not found")
        else:
            return f"API Gateway error: {response.status_code}"
    except Exception as e:
        return f"Error calling API Gateway: {str(e)}"

def process_audio_with_lex(audio_path, lex_client):
    try:
        bot_id = 'ZTEA8D6PJD'
        bot_alias_id = 'TSTALIASID'
        locale_id = 'en_US'
        session_id = 'streamlit-session'
        with open(audio_path, 'rb') as f:
            audio_bytes = f.read()
        response = lex_client.recognize_utterance(
            botId=bot_id,
            botAliasId=bot_alias_id,
            localeId=locale_id,
            sessionId=session_id,
            requestContentType='audio/l16; rate=16000; channels=1',
            responseContentType='audio/mpeg',
            inputStream=audio_bytes
        )
        return response.get("inputTranscript", "No text recognized"), response.get("audioStream")
    except Exception as e:
        return f"Error processing audio with Lex: {str(e)}", None

def extract_text_from_pdf(pdf_file):
    try:
        reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except Exception as e:
        return f"Error extracting text from PDF: {str(e)}"

def describe_image(image_file, bedrock_client):
    try:
        # Read image bytes
        image_bytes = image_file.read()
        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")
        # Prepare prompt for multimodal model
        prompt = {
            "anthropic_version": "bedrock-2023-05-31",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": image_base64}},
                        {"type": "text", "text": "Describe this image in detail."}
                    ]
                }
            ],
            "max_tokens": 200,
            "temperature": 0.5
        }
        response = bedrock_client.invoke_model(
            modelId='anthropic.claude-3-5-sonnet-20240620-v1:0',
            contentType="application/json",
            accept="application/json",
            body=json.dumps(prompt)
        )
        result = json.loads(response["body"].read())
        return result["content"][0]["text"]
    except Exception as e:
        return f"Error describing image: {str(e)}"

def main():
    st.title("\U0001F680 AWS Services Integration App")

    bedrock_client, lambda_client, lex_client = get_aws_clients()
    if not all([bedrock_client, lambda_client, lex_client]):
        st.error("AWS client init failed.")
        return

    tab1, tab2, tab3, tab4 = st.tabs([
        "\U0001F4DD Text Input",
        "\U0001F3A4 Audio Input",
        "\U0001F4C4 PDF Input",
        "\U0001F5BC Describe Image"
    ])

    with tab1:
        st.header("Text Input Processing")
        user_input = st.text_area("Enter your text:", height=150)
        direction = st.selectbox("Translation direction:", ["auto-en", "en-hi", "hi-en", "en-es", "es-en"])

        if st.button("Process Text", type="primary"):
            if user_input:
                user_input_lower = user_input.lower()
                if 'generate image' in user_input_lower:
                    prompt = user_input.replace('generate image', '').strip()
                    result = generate_image(prompt or "A beautiful landscape", bedrock_client)
                    st.image(result) if isinstance(result, Image.Image) else st.error(result)
                elif 'summarize' in user_input_lower:
                    text = user_input.replace('summarize', '').strip(':').strip()
                    result = call_lambda_summarize(text or "Please provide text", lambda_client)
                    st.success(result)
                elif 'translate' in user_input_lower:
                    text = user_input.replace('translate', '').strip(':').strip()
                    result = call_api_gateway_translate(text or "Hello world", direction)
                    st.success(result)
                else:
                    result = generate_text(user_input, bedrock_client)
                    st.write(result)
            else:
                st.warning("Enter some text first.")

    with tab2:
        st.header("Audio Input Processing")
        duration = st.slider("Recording Duration (seconds)", 1, 10, 5)
        if st.button("Record and Process Audio"):
            with st.spinner("Recording and sending to Lex..."):
                audio_path = record_audio(duration)
                recognized_text, audio_response = process_audio_with_lex(audio_path, lex_client)
                if not recognized_text.startswith("Error"):
                    st.success(f"Recognized: {recognized_text}")
                    if audio_response:
                        audio_data = audio_response.read()
                        st.audio(audio_data, format='audio/mp3')
                else:
                    st.error(recognized_text)

    with tab3:
        st.header("PDF Input Processing")
        uploaded_pdf = st.file_uploader("Upload a PDF file", type=["pdf"])

        if uploaded_pdf is not None:
            pdf_id = uploaded_pdf.name
            if st.session_state.get("current_pdf_id") != pdf_id:
                st.session_state.pdf_chat_history = []
                st.session_state.current_pdf_id = pdf_id
                st.session_state.pdf_chat_input = ""
                st.session_state.clear_pdf_input = False

            pdf_text = extract_text_from_pdf(uploaded_pdf)
            if isinstance(pdf_text, str) and pdf_text.startswith("Error"):
                st.error(pdf_text)
            else:
                st.subheader("Ask a question about the PDF")
                if "pdf_chat_history" not in st.session_state:
                    st.session_state.pdf_chat_history = []
                if "pdf_chat_input" not in st.session_state:
                    st.session_state.pdf_chat_input = ""
                if "clear_pdf_input" not in st.session_state:
                    st.session_state.clear_pdf_input = False

                # --- Clear input if needed before rendering the widget ---
                if st.session_state.clear_pdf_input:
                    st.session_state.pdf_chat_input = ""
                    st.session_state.clear_pdf_input = False

                # --- Display chat history above the input box ---
                for speaker, message in st.session_state.pdf_chat_history:
                    if speaker == "User":
                        st.markdown(f"<div style='text-align: right; color: #1a73e8;'><b>You:</b> {message}</div>", unsafe_allow_html=True)
                    else:
                        st.markdown(f"<div style='text-align: left; color: #34a853;'><b>Assistant:</b> {message}</div>", unsafe_allow_html=True)

                # --- Chat input below the history ---
                user_question = st.text_input("Your question:", key="pdf_chat_input", value=st.session_state.pdf_chat_input)
                ask_clicked = st.button("Ask", key="pdf_chat_ask")
                if ask_clicked and user_question.strip():
                    prompt = (
                        f"You are an assistant. Answer the user's question based on the following PDF content.\n\n"
                        f"PDF Content:\n{pdf_text}\n\n"
                        f"Question: {user_question}\n\n"
                        f"Answer:"
                    )
                    answer = generate_text(prompt, bedrock_client)
                    st.session_state.pdf_chat_history.append(("User", user_question))
                    st.session_state.pdf_chat_history.append(("Assistant", answer))
                    st.session_state.clear_pdf_input = True  # Set flag to clear input on next run
                 # <--- rerun to clear the input
                    

    with tab4:
        st.header("Describe Image")
        uploaded_image = st.file_uploader("Upload an image", type=["png", "jpg", "jpeg"])
        if uploaded_image is not None:
            st.image(uploaded_image, caption="Uploaded Image", use_column_width=True)
            if st.button("Describe Image"):
                with st.spinner("Describing image..."):
                    description = describe_image(uploaded_image, bedrock_client)
                    st.success(description)

if __name__ == "__main__":
    main()

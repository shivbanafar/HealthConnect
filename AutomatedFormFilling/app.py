import streamlit as st
import openai
import json
import requests
from fpdf import FPDF
import tempfile
import os
import sounddevice as sd
import numpy as np
import wave
from google.cloud import speech
import base64

# Decode base64-encoded credentials and load JSON
import base64

# Decode base64-encoded credentials and load JSON
credentials_b64 = st.secrets["GOOGLE_CREDENTIALS_BASE64"]
credentials_json = base64.b64decode(credentials_b64).decode("utf-8")
credentials_dict = json.loads(credentials_json)

# Write the credentials to a temp file
with tempfile.NamedTemporaryFile(delete=False, mode="w", suffix=".json") as temp_cred_file:
    json.dump(credentials_dict, temp_cred_file)
    GOOGLE_CREDENTIALS_PATH = temp_cred_file.name


GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

questions = [
    {"question": "Name", "type": "text"},
    {"question": "Age", "type": "number"},
    {"question": "Address", "type": "text"},
    {"question": "Contact number", "type": "number"},
    {"question": "Occupation", "type": "text"},
    {"question": "Socioeconomic status", "type": "text"},
    {"question": "Nearest health center", "type": "text"},
    {"question": "Time taken to reach health center", "type": "number"},
    {"question": "Means of transport to health center", "type": "text"},
]

# Ensure session state variables exist
if "current_step" not in st.session_state:
    st.session_state["current_step"] = 0
if "responses" not in st.session_state:
    st.session_state["responses"] = {}
if "recording_active" not in st.session_state:
    st.session_state["recording_active"] = False

# Function to record audio dynamically
def record_audio(filename):
    samplerate = 16000
    duration = 10  # Maximum duration in seconds
    st.sidebar.write("Recording... Click 'Stop Recording' when done.")
    st.session_state["recording"] = sd.rec(int(samplerate * duration), samplerate=samplerate, channels=1, dtype=np.int16)
    st.session_state["recording_active"] = True

# Function to stop recording and save file
def stop_recording(filename):
    if "recording_active" in st.session_state and st.session_state["recording_active"]:
        sd.stop()
        with wave.open(filename, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            wf.writeframes(st.session_state["recording"].tobytes())
        st.session_state["recording_active"] = False

        # Get transcription and process answer
        transcript = transcribe_audio_google(filename)
        extracted_info = process_with_gemini(transcript, questions[st.session_state["current_step"]])

        # Save the extracted answer
        current_question = questions[st.session_state["current_step"]]["question"]
        st.session_state["responses"][current_question] = extracted_info  

        # Move to next question
        if st.session_state["current_step"] < len(questions) - 1:
            st.session_state["current_step"] += 1
            st.rerun()  # This forces the UI to update with the new current_step

        os.remove(filename)

# Function to process audio input via Google Speech-to-Text
def transcribe_audio_google(audio_file):
    try:
        client = speech.SpeechClient.from_service_account_json(GOOGLE_CREDENTIALS_PATH)
        with open(audio_file, "rb") as f:
            content = f.read()
        
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US"
        )
        
        response = client.recognize(config=config, audio=audio)
        return response.results[0].alternatives[0].transcript if response.results else ""
    except Exception as e:
        print("Error in transcription:", e)
        return ""

# Function to extract relevant medical info using Gemini
def process_with_gemini(text, question):
    try:
        url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-pro:generateContent?key={GEMINI_API_KEY}"
        headers = {"Content-Type": "application/json"}
        
        payload = {
            "contents": [{"parts": [{"text": f"You are filling out a medical form. Extract the relevant answer for the question '{question['question']}' which requires a {question['type']} response, from this text: {text}"}]}]
        }

        response = requests.post(url, headers=headers, json=payload)
        response_json = response.json()

        print("Gemini API Response:", response_json)  # Debugging statement

        # Extract the response properly
        if "candidates" in response_json and response_json["candidates"]:
            extracted_text = response_json["candidates"][0]["content"]["parts"][0]["text"]
            print("Extracted Info:", extracted_text)  # Debugging statement
            return extracted_text.strip()

        print("Error: No valid response from Gemini")
        return "Error: No valid response from Gemini"
    except Exception as e:
        print("Error in Gemini API:", e)
        return f"Error: {e}"

# Streamlit UI
st.title("Medical Questionnaire - Voice Input System")

# Always-visible microphone button
st.sidebar.header("Voice Input")
recording_file = "temp_recording.wav"
if st.sidebar.button("Start Recording"):
    record_audio(recording_file)
if st.sidebar.button("Stop Recording"):
    stop_recording(recording_file)

# Display questions and progress - KEEPING ORIGINAL INTERFACE
for idx, item in enumerate(questions):
    st.subheader(item["question"])
    if idx == st.session_state["current_step"]:
        # Highlight current question and show input field with extracted answer
        st.session_state["responses"][item["question"]] = st.text_input(
            "Answer:",
            key=f"input_{idx}",  # Unique key per question
            value=st.session_state["responses"].get(item["question"], ""),
        )
    else:
        # Show non-current questions as read-only
        st.text_input(
            "Answer:",
            value=st.session_state["responses"].get(item["question"], ""),
            key=f"display_{idx}",
            disabled=True
        )

st.progress((st.session_state["current_step"] + 1) / len(questions))

# Function to export the form as a PDF
def export_to_pdf():
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, "Medical Questionnaire Report", ln=True, align='C')
    pdf.ln(10)
    
    for q, a in st.session_state["responses"].items():
        pdf.multi_cell(0, 10, f"{q}: {a}")
        pdf.ln()
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        pdf.output(tmp_file.name)
        tmp_file.close()
        with open(tmp_file.name, "rb") as file:
            st.download_button("Download PDF", file, file_name="medical_report.pdf", mime="application/pdf")
        os.remove(tmp_file.name)

# Export Button
if st.button("Export Report as PDF"):
    export_to_pdf()
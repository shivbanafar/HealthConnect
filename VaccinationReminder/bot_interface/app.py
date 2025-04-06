import streamlit as st
import google.generativeai as genai
from PIL import Image
import io
import json
import time
from dotenv import load_dotenv
import os
import random

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
text_model = genai.GenerativeModel('gemini-1.5-pro-latest')
vision_model = genai.GenerativeModel('gemini-1.5-pro-latest')

# Configure the app
st.set_page_config(
    page_title="Vaccination Assistance Chatbot",
    page_icon="💉",
    layout="wide"
)

# Initialize session state
if "messages" not in st.session_state:
    st.session_state.messages = []
if "vaccination_data" not in st.session_state:
    st.session_state.vaccination_data = None
if "vaccination_card_processed" not in st.session_state:
    st.session_state.vaccination_card_processed = False
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None
if "api_retry_count" not in st.session_state:
    st.session_state.api_retry_count = 0

def safe_generate_content(model, prompt_content, max_retries=3, initial_delay=1):
    """Wrapper for generate_content with retry logic and error handling"""
    retry_count = 0
    delay = initial_delay
    
    while retry_count < max_retries:
        try:
            response = model.generate_content(
                prompt_content,
                generation_config={"temperature": 0.3}  # Slightly more creative but still factual
            )
            return response
        except Exception as e:
            if "429" in str(e):
                retry_count += 1
                st.session_state.api_retry_count += 1
                wait_time = delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
                st.warning(f"API rate limit reached. Retry {retry_count}/{max_retries} in {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
            else:
                raise e
    
    raise Exception(f"API request failed after {max_retries} retries")

def extract_vaccination_data(image_bytes):
    """Extract vaccination details from card image with error handling"""
    prompt = """
    You are a medical document specialist analyzing a vaccination card. Extract ALL details including:
    1. PATIENT INFORMATION:
       - Full name (exact spelling)
       - Date of birth (YYYY-MM-DD format)
       - Patient ID/Health number if present
    
    2. VACCINATION HISTORY:
       - For EACH vaccine entry:
         * Vaccine name (official name)
         * Date administered (YYYY-MM-DD)
    
    3. UPCOMING VACCINES:
       - Any mentioned future vaccines
       - Recommended due dates
    
    Return STRICT JSON format (don't include any other text) with this structure:
    {
        "patient_info": {
            "name": "",
            "dob": "",
            "patient_id": ""
        },
        "vaccines_received": [
            {
                "name": "",
                "date": ""
            }
        ],
        "due_vaccines": [
            {
                "name": "",
                "due_date": ""
            }
        ]
    }
    """
    
    try:
        image = Image.open(io.BytesIO(image_bytes))
        response = safe_generate_content(
            vision_model,
            [prompt, image]
        )
        
        # Clean response to extract JSON
        response_text = response.text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        elif '```' in response_text:
            response_text = response_text.split('```')[1]
        
        return json.loads(response_text)
    except Exception as e:
        st.error(f"Error processing card: {str(e)}")
        return None

def get_vaccine_precautions(vaccine_name):
    """Get 2-3 precautions for a specific vaccine with fallback"""
    try:
        prompt = f"""
        Provide exactly 2-3 important precautions for someone about to receive a {vaccine_name} vaccine.
        Return as a JSON array only:
        {{
            "precautions": []
        }}
        """
        
        response = safe_generate_content(text_model, prompt)
        response_text = response.text
        if '```json' in response_text:
            response_text = response_text.split('```json')[1].split('```')[0]
        return json.loads(response_text)["precautions"]
    except Exception:
        # Fallback precautions if API fails
        fallback_precautions = {
            "COVID-19": [
                "Monitor for allergic reactions for 15-30 minutes after vaccination",
                "Inform your doctor about any history of blood clotting disorders",
                "Stay hydrated and rest after vaccination"
            ],
            "Flu": [
                "Inform your doctor if you have egg allergies",
                "Avoid vaccination if you currently have a fever",
                "Mild flu-like symptoms are common for 1-2 days after vaccination"
            ],
            "default": [
                "Consult your doctor before vaccination",
                "Inform about any allergies or medical conditions",
                "Stay at the clinic for observation for 15-30 minutes after vaccination"
            ]
        }
        
        return fallback_precautions.get(vaccine_name, fallback_precautions["default"])

def process_uploaded_file(uploaded_file):
    """Process uploaded vaccination card file with enhanced error handling"""
    try:
        # Reset previous state for new upload
        st.session_state.vaccination_card_processed = False
        st.session_state.vaccination_data = None
        
        file_bytes = uploaded_file.getvalue()
        
        if uploaded_file.type not in ["image/jpeg", "image/png"]:
            return {"error": "Only JPEG/PNG images are supported"}
        
        st.image(file_bytes, caption="Uploaded Vaccination Card", use_column_width=True)
        
        with st.spinner("Analyzing vaccination card..."):
            vaccine_data = extract_vaccination_data(file_bytes)
            if vaccine_data:
                # Add precautions for due vaccines
                if "due_vaccines" in vaccine_data:
                    for vaccine in vaccine_data["due_vaccines"]:
                        vaccine["precautions"] = get_vaccine_precautions(vaccine["name"])
                
                st.session_state.vaccination_data = vaccine_data
                st.session_state.vaccination_card_processed = True
                st.session_state.last_uploaded_file = uploaded_file.name
                return {"success": True, "data": vaccine_data}
            else:
                return {"error": "Failed to extract vaccination data"}
                
    except Exception as e:
        return {"error": f"File processing error: {str(e)}"}

def render_instructions():
    with st.expander("ℹ️ How to Use This Chatbot", expanded=True):
        st.markdown("""
        **Welcome to the Vaccination Assistance Chatbot!** Here's how to use it:

        1. **Upload Your Vaccination Card**
           - Click 'Browse files' in the sidebar
           - Select a clear photo of your vaccination card (JPEG/PNG)
           - Wait for the system to process your card

        2. **View Your Vaccination Details**
           - After processing, your vaccination history will appear
           - See upcoming due vaccines with precautions
           - Check your personal information for accuracy

        3. **Ask Questions**
           - Type your questions in the chat box below
           - Get personalized answers based on your vaccination records
           - Ask about vaccine schedules, side effects, travel vaccines, etc.

        4. **Get Reminders**
           - The system will show upcoming vaccine due dates
           - See important precautions for each vaccine

        **Tips for Best Results:**
        - Ensure your vaccination card photo is clear and well-lit
        - Check that all text on the card is readable
        - Ask specific questions for the most accurate answers
        """)

def render_sidebar():
    with st.sidebar:
        st.header("📄 Upload Vaccination Card")
        uploaded_file = st.file_uploader(
            "Choose your vaccination card image (JPEG/PNG)",
            type=["jpg", "jpeg", "png"],
            key="vaccine_card_uploader"
        )
        
        if uploaded_file is not None:
            if (st.session_state.last_uploaded_file != uploaded_file.name or 
                not st.session_state.vaccination_card_processed):
                
                result = process_uploaded_file(uploaded_file)
                if "error" in result:
                    st.error(result["error"])
                else:
                    st.success("Vaccination card processed successfully!")
                    if st.session_state.api_retry_count > 0:
                        st.info(f"Note: Some requests required retries due to API limits. Total retries: {st.session_state.api_retry_count}")
                    st.balloons()

def generate_chat_response(prompt):
    """Generate appropriate response based on user prompt and available data"""
    current_date = time.strftime('%Y-%m-%d')
    
    # System prompt for generic vaccination questions
    generic_prompt = """
    You are a Vaccination Expert Assistant with the following capabilities:
    
    1. For GENERAL vaccination questions (without personal data):
    - Provide accurate, up-to-date information about vaccines
    - Explain vaccine schedules, side effects, precautions
    - Offer travel vaccination advice
    - Compare different vaccine brands
    - Explain vaccine efficacy and duration
    
    2. For PERSONALIZED questions (when vaccination card is uploaded):
    - Answer based on the user's specific vaccination history
    - Identify missing vaccines based on age/health conditions
    - Calculate due dates for next doses
    - Provide personalized precautions
    
    3. Response Guidelines:
    - Be concise but thorough (3-5 sentences for most answers)
    - Use bullet points for lists of side effects/precautions
    - Always cite reputable sources when possible
    - If unsure, recommend consulting a healthcare provider
    - For age/condition specific advice, ask for clarification if needed
    
    Current Date: {current_date}
    """
    
    if st.session_state.vaccination_card_processed:
        # Personalized response with vaccination data
        vaccination_context = f"""
        User's Vaccination Data:
        {json.dumps(st.session_state.vaccination_data, indent=2)}
        """
        
        full_prompt = f"{generic_prompt}\n\n{vaccination_context}\n\nQuestion: {prompt}"
    else:
        # Generic response without personal data
        full_prompt = f"{generic_prompt}\n\nQuestion: {prompt}"
    
    try:
        response = safe_generate_content(text_model, full_prompt)
        return response.text
    except Exception as e:
        return f"Sorry, I'm having trouble answering right now. Please try again later. (Error: {str(e)})"

def render_chat_interface():
    st.title("💉 Vaccination Assistance Chatbot")
    render_instructions()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("Ask about your vaccinations..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = generate_chat_response(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})

def render_vaccination_details():
    if st.session_state.vaccination_card_processed:
        st.subheader("📋 Your Vaccination Records")
        data = st.session_state.vaccination_data
        
        with st.expander("👤 Personal Information"):
            if "patient_info" in data:
                st.write(f"**Name:** {data['patient_info'].get('name', 'N/A')}")
                st.write(f"**Date of Birth:** {data['patient_info'].get('dob', 'N/A')}")
                st.write(f"**Patient ID:** {data['patient_info'].get('patient_id', 'N/A')}")
        
        with st.expander("💉 Vaccination History"):
            if "vaccines_received" in data and data["vaccines_received"]:
                for vax in data["vaccines_received"]:
                    st.write(f"**{vax.get('name', 'Vaccine')}**")
                    st.write(f"- Date: {vax.get('date', 'N/A')}")
                    st.write("---")
            else:
                st.write("No vaccination history found")
        
        with st.expander("⚠️ Upcoming Vaccines & Precautions"):
            if "due_vaccines" in data and data["due_vaccines"]:
                for vax in data["due_vaccines"]:
                    st.write(f"**{vax.get('name', 'Vaccine')}**")
                    st.write(f"- Due Date: {vax.get('due_date', 'N/A')}")
                    
                    if "precautions" in vax:
                        st.write("- Precautions:")
                        for precaution in vax["precautions"]:
                            st.write(f"  • {precaution}")
                    
                    st.write("---")
            else:
                st.write("No upcoming vaccines found")

# Main App Flow
render_sidebar()
render_chat_interface()
render_vaccination_details()
# HealthConnect: Bridging Healthcare Gaps in Underserved Communities

## Problem Statement
**Lack of Access to Healthcare in Underserved Communities**  
Many communities, especially in rural and remote areas, lack access to basic healthcare services. This results in poor health outcomes, preventable diseases, and reduced quality of life.  
Barriers include:
- Inadequate healthcare infrastructure
- Shortage of medical professionals
- Limited awareness of preventive care

### Objective
Create innovative, scalable, and sustainable solutions to improve access to healthcare in underserved communities.  
**Aligned with UN SDG 3**: _Good Health and Well-being_ – Ensure healthy lives and promote well-being for all at all ages.

---

## 💡 Solution Overview
HealthConnect addresses key challenges faced in rural and underserved areas:
- Shortage of trained medical professionals
- Lack of access to nearby medical centers
- Language barriers during medical consultations
- Limited awareness of preventive healthcare

Visit the deployed app: **[https://healthconnect.streamlit.app](https://healthconnect.streamlit.app)**  
**Built using Streamlit**

---

## 🚀 Key Features

### 1. Hospital and Medical Centre Blindspot Analyzer
Identifies gaps in healthcare access by analyzing hospital locations and travel feasibility within the "golden hour" – the crucial first hour after a medical emergency.

#### Capabilities:
- Retrieves hospital data within a specified radius
- Prioritizes multispecialty hospitals
- Calculates optimal routes considering:
  - Real-time traffic
  - Speed limits
- Identifies underserved areas and displays "blind spots" on an interactive map

#### APIs Used:
- Google Maps JavaScript API  
- Google Places API  
- Google Geocoding API  
- Google Routes API  
- Google Roads API

---

### 2. Automated Voice-Powered Form Filling
Streamlines medical history intake using voice input and AI-powered NLP, reducing workload and bridging language gaps.

#### Features:
- Chronological medical questionnaire form
- Voice input using Google Speech-to-Text
- NLP via Gemini to analyze and auto-fill responses
- Progress bar and easy-to-navigate interface
- One-click **Export to PDF** for patient reports

#### Benefits:
- Reduces dependency on large medical staff
- Accelerates initial patient evaluation
- Overcomes language and literacy barriers
- Improves patient-doctor efficiency

---

### 3. Vaccination Assistant Chatbot
An intelligent assistant that guides patients through their vaccination journey using computer vision and AI chat.

#### Functionality:
- Analyzes uploaded vaccination card images (handwritten) using Gemini Vision AI
- Extracts vaccination history, due doses, and schedules
- Provides:
  - Patient-specific upcoming vaccinations
  - Safety tips and side effects
  - Personalized conversation in local languages
- Presents organized dashboard with due date reminders and alerts

#### Highlights:
- Dynamic chatbot handles FAQs, precautions, and alerts
- Session management and conversational memory
- Simple and clear language for non-medical users
- Designed for low-literacy and elderly populations

---

## 🧠 Tech Stack
- **Streamlit** (Web App Framework)
- **Google Gemini (Vision + NLP)**
- **Google Speech-to-Text API**
- **Google Maps Platform APIs**
- **Python** (Backend)
- **PDF generation** for downloadable reports

---

## 🌍 Impact
HealthConnect enables:
- Efficient patient triaging and documentation
- Smarter navigation and emergency planning
- Increased vaccination awareness and understanding
- Scalable, AI-assisted solutions for low-resource areas

This project contributes to **UN SDG 3 – Good Health and Well-being**, helping underserved communities receive the healthcare support they deserve.

---

## 🔗 Live Demo
Visit: [https://healthconnect.streamlit.app](https://healthconnect.streamlit.app)

---

## 📄 License
This project is open-source under the MIT License.

---

## 🤝 Contributing
Have ideas to improve or expand the project? Feel free to submit issues or pull requests. Collaboration is welcome.

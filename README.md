# 🏛️ SchemeAssist – XAI Platform

An AI-powered decision support system for government schemes using **RAG (Retrieval-Augmented Generation)**, **Machine Learning**, and **Explainable AI (XAI)**.

---

## 🚀 Features

- 🔍 AI Chatbot to find relevant government schemes
- 🧠 RAG-based retrieval using semantic search
- 🤖 ML-based eligibility prediction (Random Forest)
- 📊 Explainable AI (XAI) for decision transparency
- 📄 Application form with document upload
- 📧 Email notification with results
- 🧑‍💼 Agent Portal to review applications
- 📥 Downloadable application report

---

## 🧠 Technologies Used

- Python
- Streamlit (UI)
- SentenceTransformers (Embeddings)
- Gemini / LLM API (for chatbot)
- Scikit-learn (ML Model)
- Pandas (Data Processing)

---

## ⚙️ System Architecture

1. User interacts with chatbot  
2. RAG retrieves relevant schemes  
3. LLM generates response  
4. User fills application form  
5. ML model predicts approval  
6. XAI explains decision  
7. Result sent via email  
8. Application stored for agent review  

---

## 📊 Dataset

- Government schemes dataset (structured)
- Features used:
  - Income
  - Employment
  - Category
- Target:
  - Approval (simulated)

---

## ⚠️ Note

- This project uses simulated data for ML predictions  
- API keys are not included for security reasons  

---

## ▶️ How to Run

```bash
streamlit run app.py


# 🌐 Agentic Web Search

**Agentic Web Search** is an AI-powered project that performs intelligent web searches and summarization using an agentic approach.  
It integrates a backend API (Python) with a React-based frontend for seamless user experience.

🔗 **Live Demo:** [https://abitseb143.github.io/agentic-web-search](https://abitseb143.github.io/agentic-web-search)

---

## ✨ Features

- 🔍 **Smart Search:** Performs real-time Google-like searches with contextual AI summarization.
- 🧠 **AI-Powered Summaries:** Uses OpenAI/LLM API to generate meaningful summaries from fetched content.
- ⚡ **Modern UI:** Built with React + Vite for a fast, interactive frontend experience.
- 🧩 **Modular Backend:** Python-based backend (Flask/FastAPI-ready) that handles API calls and logic.
- 🌍 **Deployed on GitHub Pages:** Fully hosted frontend, accessible via the link above.

---

## 🖼️ Frontend Preview

Here’s how the frontend looks when running live 👇  

### 🔹 Homepage
A clean, minimal search interface with a centered input field and search button.

### 🔹 Search Results
Displays the top web results fetched from APIs, each with:
- Website title & link  
- Short description snippet  
- AI-generated summary  

You can see it in action here:  
👉 [**Live Frontend**](https://abitseb143.github.io/agentic-web-search)

---

## 🧱 Tech Stack

| Layer | Technology Used |
|-------|------------------|
| **Frontend** | React + Vite |
| **Backend** | Python (Flask / FastAPI) |
| **AI Layer** | OpenAI API |
| **Web Scraping** | BeautifulSoup, Requests |
| **Environment Management** | dotenv |
| **Hosting** | GitHub Pages (Frontend) |

---

## ⚙️ Local Setup

### 1. Clone this repository
```bash
git clone https://github.com/Abitseb143/agentic-web-search.git
cd agentic-web-search

2. Run the backend
cd backend
pip install -r requirements.txt
python agentic_search.py

3. Run the frontend locally
cd frontend
npm install
npm run dev

import streamlit as st
import sys
import os

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

st.set_page_config(
    page_title="Auto Job Agent",
    page_icon="💼",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("💼 Auto Job Application Agent")
st.markdown("""
Welcome to your self-hosted, autonomous job search agent.

Please navigate using the sidebar to configure your agent:
1. **Settings**: Configure your LLM brains (Ollama, Gemini, OpenRouter).
2. **Profile**: Upload your resume and fill out your details.
3. **Dashboard**: Monitor live executions and review applications.
""")

import streamlit as st
import sys
import os
import importlib

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

import src.core.crud
importlib.reload(src.core.crud)
from src.core.crud import get_all_llm_configs, save_llm_config, delete_llm_config


def test_llm_connection(model_name, api_key, base_url, provider=""):
    from src.agent.langchain_llm import build_llm
    try:
        config = {
            "model_name": model_name,
            "api_key": api_key,
            "base_url": base_url,
            "provider": provider
        }
        llm = build_llm(config, temperature=0.0, max_tokens=10)
        llm.invoke('Say the word test')
        return True, '✅ Connection successful! Model is active.'
    except Exception as e:
        return False, f'❌ Failed: {str(e)}'

st.set_page_config(page_title="Brain Settings", page_icon="🧠")

st.title("🧠 Agent Brain Settings")

with st.expander("📖 How to Setup Your Agent's Brain & Fallbacks (Click to Read)", expanded=True):
    st.markdown("""
    **What is this page?**
    The Job Agent needs an AI "Brain" (LLM) to read job descriptions and score your matches. This page lets you connect to providers like Groq, OpenAI, or Ollama.
    
    **How to set it up:**
    1. Click **➕ Add New Brain Configuration** below.
    2. **Provider:** Select where your model is hosted (e.g., Groq).
    3. **Model Name:** Enter the exact model ID (e.g., `llama3-70b-8192` or `gpt-4o-mini`).
    4. **Base URL:** Only needed if using custom endpoints (like Ollama). For Groq, it auto-fills to `https://api.groq.com/openai/v1`.
    5. **API Key:** Paste your secret key from the provider.
    
    **💡 The Fallback Superpower (Priority System):**
    You can add multiple models! 
    - Give your favorite model **Priority 1**.
    - Add a second model (or even a second API key) as **Priority 2**.
    - *Why?* Free tiers (like Groq) have strict rate limits. If your Priority 1 model hits a `429 Rate Limit` while scanning 100 jobs, the agent won't crash! It will instantly and seamlessly failover to your Priority 2 model to finish the job.
    """)

# Load existing configurations
existing_configs = get_all_llm_configs()
config_dict = {c['provider']: c for c in existing_configs}

providers = ["Groq (Recommended)", "OpenAI", "Ollama (Local)", "OpenRouter", "Gemini"]

# Add New Configuration
with st.expander("➕ Add New Brain Configuration", expanded=False):
    with st.form("form_new_config"):
        col1, col2 = st.columns(2)
        with col1:
            provider_selection = st.selectbox("Provider", providers)
        with col2:
            is_active = st.checkbox("Enable Provider", value=True)
            
        priority = st.number_input("Priority (1 = Highest, Fallback sequence)", min_value=1, max_value=20, value=1)
        
        model_name = st.text_input("Model Name (e.g., llama3-70b-8192, gpt-4o-mini)")
        base_url = st.text_input("Base URL (Optional, e.g., https://api.groq.com/openai/v1 or http://localhost:11434)")
        api_key = st.text_input("API Key", type="password")
        
        col_save, col_test = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("Add Brain")
        with col_test:
            tested = st.form_submit_button("🧪 Test Connection")
        
        if tested:
            if not model_name:
                st.error("Model Name is required to test.")
            else:
                db_provider = provider_selection.split(" ")[0].lower()
                test_base = base_url
                if not test_base:
                    if db_provider == "groq": test_base = "https://api.groq.com/openai/v1"
                    elif db_provider == "ollama": test_base = "http://localhost:11434"
                with st.spinner("Testing connection..."):
                    success, msg = test_llm_connection(model_name, api_key, test_base, db_provider)
                    if success: st.success(msg)
                    else: st.error(msg)
        
        if submitted:
            if is_active and not model_name:
                st.error("Model Name is required if the provider is enabled.")
            else:
                db_provider = provider_selection.split(" ")[0].lower()
                
                # Auto-fill base URL if missing for known providers
                if not base_url:
                    if db_provider == "groq": base_url = "https://api.groq.com/openai/v1"
                    elif db_provider == "ollama": base_url = "http://localhost:11434"
                
                save_llm_config(
                    provider=db_provider,
                    api_key=api_key,
                    base_url=base_url,
                    model_name=model_name,
                    priority=priority,
                    is_active=is_active
                )
                st.success("New Brain added successfully!")
                st.rerun()

st.divider()

# Existing Configurations List
st.subheader("Current Brain Hierarchy (Failover Sequence)")
if existing_configs:
    existing_configs.sort(key=lambda x: (not x['is_active'], x['priority']))
    
    for conf in existing_configs:
        is_act = "✅ Active" if conf['is_active'] else "⏸️ Disabled"
        with st.expander(f"Priority {conf['priority']} : {conf['provider'].capitalize()} - {conf['model_name']} ({is_act})"):
            with st.form(f"form_edit_{conf['id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    edit_is_active = st.checkbox("Enable", value=bool(conf['is_active']))
                with col2:
                    edit_priority = st.number_input("Priority", value=conf['priority'])
                
                edit_model = st.text_input("Model Name", value=conf['model_name'])
                edit_base_url = st.text_input("Base URL", value=conf['base_url'] or "")
                edit_api_key = st.text_input("API Key", type="password", value=conf['api_key'] or "")
                
                col_save, col_test, col_del = st.columns(3)
                with col_save:
                    if st.form_submit_button("Save Changes"):
                        save_llm_config(
                            provider=conf['provider'],
                            api_key=edit_api_key,
                            base_url=edit_base_url,
                            model_name=edit_model,
                            priority=edit_priority,
                            is_active=edit_is_active,
                            config_id=conf['id']
                        )
                        st.success("Updated!")
                        st.rerun()
                with col_test:
                    if st.form_submit_button("🧪 Test"):
                        with st.spinner("Testing..."):
                            success, msg = test_llm_connection(edit_model, edit_api_key, edit_base_url, conf['provider'])
                            if success: st.success(msg)
                            else: st.error(msg)
                with col_del:
                    if st.form_submit_button("🗑️ Delete"):
                        delete_llm_config(conf['id'])
                        st.warning("Deleted!")
                        st.rerun()
else:
    st.warning("No active Brains configured! The agent will not be able to evaluate jobs.")

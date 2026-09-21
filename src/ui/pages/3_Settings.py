import streamlit as st
import sys
import os

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

from src.core.crud import get_all_llm_configs, save_llm_config, delete_llm_config

st.set_page_config(page_title="Settings - LLM Config", page_icon="⚙️")

st.title("⚙️ Brain Configuration")
st.markdown("Configure your AI providers. The agent will attempt to use Priority 1 first, and automatically failover if a rate limit or error occurs.")

# Load existing configurations
existing_configs = get_all_llm_configs()
config_dict = {c['provider']: c for c in existing_configs}

providers = ["Ollama (Local)", "Gemini", "OpenRouter", "OmniRoute"]

for provider in providers:
    db_provider_name = provider.split(" ")[0].lower()
    current_config = config_dict.get(db_provider_name, {})
    
    with st.expander(f"Configure {provider}", expanded=bool(current_config)):
        with st.form(f"form_{db_provider_name}"):
            is_active = st.checkbox("Enable Provider", value=bool(current_config.get("is_active", False)))
            priority = st.number_input("Priority (1 = Highest)", min_value=1, max_value=10, value=current_config.get("priority", 1))
            
            # Default models based on provider
            default_model = ""
            if db_provider_name == "ollama":
                default_model = "llama3"
            elif db_provider_name == "gemini":
                default_model = "gemini-1.5-flash"
            
            model_name = st.text_input("Model Name", value=current_config.get("model_name", default_model))
            
            # Base URL is mainly for Ollama or custom endpoints
            base_url = st.text_input("Base URL (Optional)", value=current_config.get("base_url", "http://localhost:11434" if db_provider_name == "ollama" else ""))
            
            # API Key (Ollama usually doesn't need one)
            api_key = st.text_input("API Key", type="password", value=current_config.get("api_key", ""))
            
            submitted = st.form_submit_button("Save Configuration")
            
            if submitted:
                if is_active and not model_name:
                    st.error("Model Name is required if the provider is enabled.")
                else:
                    save_llm_config(
                        provider=db_provider_name,
                        api_key=api_key,
                        base_url=base_url,
                        model_name=model_name,
                        priority=priority,
                        is_active=is_active
                    )
                    st.success(f"{provider} configuration saved successfully!")
                    
# Display Active Fallback Order
st.subheader("Active Fallback Sequence")
active_configs = [c for c in get_all_llm_configs() if c['is_active']]
if active_configs:
    active_configs.sort(key=lambda x: x['priority'])
    for idx, conf in enumerate(active_configs):
        st.write(f"**{idx + 1}.** {conf['provider'].capitalize()} (`{conf['model_name']}`)")
else:
    st.warning("No active LLM providers configured. The agent will not be able to run.")

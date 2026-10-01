import streamlit as st
import os
import json

st.set_page_config(page_title="Norvi Account", page_icon="🛡️", layout="wide")

st.markdown("""
    <div style='background: rgba(0, 0, 0, 0.85); color: #fff; padding: 12px 24px; border-radius: 8px; font-weight: 600; font-size: 20px; display: inline-block; margin-bottom: 20px;'>
        🛡️ Norvi Agent Configuration
    </div>
""", unsafe_allow_html=True)

st.title("Agency Activation Details")
st.markdown("Your agent is securely activated and bound to this device.")

LEASE_FILE = os.path.expanduser("~/.norvi_rolvio_lease")

def load_lease():
    if os.path.exists(LEASE_FILE):
        try:
            with open(LEASE_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return None

lease = load_lease()

if lease:
    st.text_input("Agency Email", value=lease.get("email", ""), disabled=True)
    st.text_input("Activation Key", value="••••••••••••••••••••••••", type="password", disabled=True)
    st.text_input("Hardware ID Bound", value=lease.get("hwid", "Unknown"), disabled=True)
    st.success("Your agent is successfully authenticated and locked to the Norvi cloud model.")
else:
    st.error("No active lease found. Please restart the app and activate.")

st.divider()
st.subheader("Automated Brain Status")
st.info("Your AI brain is centrally managed by Norvi. No API keys are required. The engine automatically connects to the dedicated local Ollama proxy (gemma4:cloud).")

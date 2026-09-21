import streamlit as st
import sys
import os
import subprocess

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

st.set_page_config(page_title="Session Manager", page_icon="🔐")

st.title("🔐 Browser Session Manager")
st.markdown("""
To apply to jobs autonomously, the agent needs to be logged into your job platforms. 
Because we do not store passwords, you will log in **once** manually. The agent will save your session cookies and reuse them in the background.
""")

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storageState.json")

st.subheader("Current Status")
if os.path.exists(STATE_FILE):
    st.success("✅ Active session cookies found! (`storageState.json` exists)")
    if st.button("Delete Session (Log Out)"):
        os.remove(STATE_FILE)
        st.rerun()
else:
    st.warning("❌ No active session found. The agent cannot apply to jobs until you log in.")

st.divider()

st.subheader("Record New Session")
st.markdown("Clicking the button below will open a new visible browser window. **Log into LinkedIn manually**, and then **close the browser window** to save the session.")

platform = st.selectbox("Select Platform", ["LinkedIn", "Indeed", "Naukri", "Wellfound"])

urls = {
    "LinkedIn": "https://www.linkedin.com/login",
    "Indeed": "https://secure.indeed.com/auth",
    "Naukri": "https://www.naukri.com/nlogin/login",
    "Wellfound": "https://wellfound.com/login"
}

if st.button(f"Launch {platform} Login Window"):
    login_url = urls[platform]
    script_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "auth", "generate_session.py")
    
    with st.spinner("Launching browser... Please check your taskbar!"):
        try:
            # We run this as a subprocess so it doesn't block the Streamlit thread completely,
            # but we wait for it to finish.
            subprocess.run([
                sys.executable, 
                script_path, 
                "--platform", platform.lower(), 
                "--url", login_url,
                "--output", STATE_FILE
            ], check=True)
            st.success(f"Session for {platform} saved successfully!")
            st.rerun()
        except subprocess.CalledProcessError as e:
            st.error(f"Failed to record session: {e}")

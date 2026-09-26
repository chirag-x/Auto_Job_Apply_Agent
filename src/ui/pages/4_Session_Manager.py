import streamlit as st
import sys
import os
import subprocess

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

st.set_page_config(page_title="Session Manager", page_icon="🔑")

st.title("🔑 Browser Session Manager")
st.markdown("""
To apply to jobs autonomously, the agent needs to be logged into your job platforms.
Because we do not store passwords, you will log in **once** manually. The agent will save your session cookies and reuse them in the background.
""")

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

PLATFORMS = {
    "LinkedIn":    {"file": "storageState.json",            "url": "https://www.linkedin.com/login",       "icon": "🔵"},
    "Naukri":      {"file": "storageState_naukri.json",     "url": "https://www.naukri.com/nlogin/login",  "icon": "🟠"},
    "Internshala": {"file": "storageState_internshala.json","url": "https://internshala.com/login/user",   "icon": "🟢"},
    "Wellfound":   {"file": "storageState_wellfound.json",  "url": "https://wellfound.com/login",          "icon": "🚀"},
    "Indeed":      {"file": "storageState_indeed.json",     "url": "https://secure.indeed.com/auth",       "icon": "🌐"},
}

# ── Status overview ────────────────────────────────────────────────────────────
st.subheader("📊 Session Status Overview")
cols = st.columns(len(PLATFORMS))
for idx, (name, info) in enumerate(PLATFORMS.items()):
    state_path = os.path.join(ROOT_DIR, info["file"])
    with cols[idx]:
        if os.path.exists(state_path):
            st.success(f"{info['icon']} **{name}**\n\n✅ Active")
        else:
            st.warning(f"{info['icon']} **{name}**\n\n❌ Not logged in")

st.divider()

# ── Record new session ─────────────────────────────────────────────────────────
st.subheader("🔐 Record New Session")
st.markdown("""
1. Select a platform below
2. Click **Launch Login Window** (or **Verify Browser** if already logged in)
3. A visible browser will open. Log in manually, OR verify your profile if already logged in.
4. **Close the browser window** when done — session is saved automatically
""")

platform = st.selectbox("Select Platform to Login", list(PLATFORMS.keys()))
info = PLATFORMS[platform]
state_file = os.path.join(ROOT_DIR, info["file"])

col_status, col_action = st.columns([2, 1])
with col_status:
    if os.path.exists(state_file):
        st.success(f"✅ Active session found for **{platform}**")
    else:
        st.warning(f"⚠️ No session found for **{platform}**")

with col_action:
    if os.path.exists(state_file):
        if st.button(f"🗑️ Delete {platform} Session", type="secondary"):
            os.remove(state_file)
            st.success(f"{platform} session deleted.")
            st.rerun()

btn_text = f"🌐 Launch Browser to Verify / Edit {platform} Profile" if os.path.exists(state_file) else f"🔑 Launch {platform} Login Window"
if st.button(btn_text, type="primary"):
    script_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        "auth", "generate_session.py"
    )
    with st.spinner(f"Launching browser for {platform}... Check your taskbar!"):
        try:
            subprocess.run([
                sys.executable,
                script_path,
                "--platform", platform.lower(),
                "--url", info["url"] if not os.path.exists(state_file) else "https://" + info["url"].split("/")[2], 
                "--output", state_file
            ], check=True)
            st.success(f"✅ Session for **{platform}** saved successfully!")
            st.rerun()
        except subprocess.CalledProcessError as e:
            st.error(f"Failed to record session: {e}")

st.divider()

# ── Clear all sessions ─────────────────────────────────────────────────────────
st.subheader("🧹 Clear All Sessions")
if st.button("Delete ALL Sessions (Full Logout)", type="secondary"):
    deleted = 0
    for name, info in PLATFORMS.items():
        path = os.path.join(ROOT_DIR, info["file"])
        if os.path.exists(path):
            os.remove(path)
            deleted += 1
    st.success(f"Deleted {deleted} session file(s). You are now fully logged out.")
    st.rerun()

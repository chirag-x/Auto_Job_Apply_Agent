import streamlit as st
import sys
import os
import pandas as pd
import subprocess

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.db import get_db_connection

st.set_page_config(
    page_title="Mission Control | Rolvio",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- BRANDING OVERLAY ---
st.markdown("""
    <div style='position: fixed; bottom: 20px; left: 20px; background: rgba(0, 0, 0, 0.85); color: #fff; padding: 8px 16px; border-radius: 20px; font-weight: 600; font-size: 14px; z-index: 9999; border: 1px solid #333;'>
        🛡️ Norvi Agent
    </div>
""", unsafe_allow_html=True)


st.title("🚀 Rolvio Mission Control")
st.markdown("Your autonomous job search command center.")

# --- ONBOARDING / SETUP ---
st.info("👋 **Welcome to Rolvio!** If this is your first time, please run the quick setup guide to configure your agent.")
if st.button("🚀 Run Setup Guide & Configuration", use_container_width=True, type="primary"):
    st.switch_page("pages/3_Norvi_Account.py")

st.divider()

# --- System Status ---
st.subheader("System Status")

with get_db_connection() as conn:
    total_jobs = conn.execute("SELECT COUNT(*) FROM job_applications").fetchone()[0]
    total_applied = conn.execute("SELECT COUNT(*) FROM job_applications WHERE status IN ('applied', 'assessment', 'interview_invite', 'offer', 'rejected', 'failed')").fetchone()[0]
    total_interviews = conn.execute("SELECT COUNT(*) FROM job_applications WHERE status IN ('interview_invite', 'offer')").fetchone()[0]
    
col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Jobs Found", total_jobs)
col2.metric("Total Applications Sent", total_applied)
col3.metric("Interviews Secured", total_interviews)

invite_rate = f"{(total_interviews / total_applied * 100):.1f}%" if total_applied > 0 else "0.0%"
col4.metric("Interview Invite Rate", invite_rate)

st.divider()

# --- Master Controls ---
st.subheader("⚙️ Master Controls")
st.markdown("Quickly launch background processes. (For detailed settings, use the specific pages in the sidebar).")

c1, c2, c3 = st.columns(3)

with c1:
    st.info("**1. Aggregate New Jobs**")
    st.caption("Runs the job scrapers across all active platforms to find new roles.")
    if st.button("Launch Job Aggregator", use_container_width=True):
        st.switch_page("pages/5_Job_Aggregator.py")

with c2:
    st.warning("**2. Execution Engine**")
    st.caption("Launches the Playwright bots to autonomously apply to pending jobs.")
    if st.button("Launch Execution Engine", use_container_width=True):
        st.switch_page("pages/5_Job_Aggregator.py")

with c3:
    st.success("**3. Email Scanner**")
    st.caption("Scans your linked inboxes for Interview invites and updates the Kanban.")
    if st.button("Scan Inbox Now", use_container_width=True):
        st.switch_page("pages/6_Interview_Tracker.py")
        
st.divider()

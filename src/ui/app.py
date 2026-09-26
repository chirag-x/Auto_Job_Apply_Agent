import streamlit as st
import sys
import os
import pandas as pd
import subprocess

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.core.db import get_db_connection

st.set_page_config(
    page_title="Mission Control | Auto Job Agent",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🚀 Mission Control")
st.markdown("Your autonomous job search command center.")

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
st.subheader("⚡ Master Controls")
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

# --- Recent Activity Feed ---
st.subheader("📡 Live Activity Feed")

with get_db_connection() as conn:
    query = """
        SELECT company, job_title, platform, status, applied_at, logs 
        FROM job_applications 
        ORDER BY applied_at DESC 
        LIMIT 20
    """
    df_activity = pd.read_sql_query(query, conn)

if df_activity.empty:
    st.write("No activity yet. Start the Job Aggregator!")
else:
    # Build a visual terminal-like feed
    feed_html = "<div style='background-color:#1E1E1E; color:#D4D4D4; padding:20px; border-radius:10px; font-family:monospace; height:400px; overflow-y:scroll;'>"
    
    for _, row in df_activity.iterrows():
        time_str = str(row['applied_at'])[:16] if pd.notna(row['applied_at']) else "Unknown Time"
        status_color = "#4CAF50" if row['status'] in ['applied', 'interview_invite', 'offer'] else "#FF9800" if row['status'] == 'assessment' else "#F44336" if row['status'] in ['rejected', 'failed'] else "#9E9E9E"
        
        # Do not use indentation for HTML inside markdown to avoid triggering code blocks
        feed_html += f"""<div style='margin-bottom: 10px; border-bottom: 1px solid #333; padding-bottom: 10px;'>
<span style='color:#569CD6;'>[{time_str}]</span> 
<span style='color:#4EC9B0;'>[{row['platform'].upper()}]</span> 
<span style='color:{status_color}; font-weight:bold;'>[{row['status'].upper()}]</span> 
<b>{row['company']}</b> - {row['job_title']}
<br>
<span style='color:#808080; font-size:0.9em;'> > {str(row['logs'])[:150]}...</span>
</div>"""
    feed_html += "</div>"
    st.markdown(feed_html, unsafe_allow_html=True)

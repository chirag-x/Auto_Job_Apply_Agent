import streamlit as st
import sqlite3
import pandas as pd
import asyncio
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.core.db import get_db_connection

st.set_page_config(page_title="Interview Tracker", page_icon="📊", layout="wide")

st.title("📊 Autonomous Interview Tracker (Kanban)")
st.markdown("Monitor your job applications across their lifecycle. The AI Email Parser will automatically read your inbox for Interview Invites, Coding Tests, and Rejections, updating this board in real-time.")

# --- Email Settings ---
with st.expander("⚙️ Email Parser Settings (IMAP)"):
    st.info("You can link multiple email accounts (e.g. Main, Burner 1) to scan for interview updates.")
    
    st.markdown("""
    **Google/Gmail Setup Instructions:**
    1. Go to your **Google Account** settings -> **Security**.
    2. Search for **App Passwords** in the search bar.
    3. Create a new App Password (name it 'Aoto').
    4. Paste the 16-character password into the 'App Password' field below.
    5. **Crucial:** Ensure IMAP is enabled in Gmail (Gear Icon -> See all settings -> Forwarding and POP/IMAP -> Enable IMAP).
    """)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_credentials ORDER BY id ASC")
        all_creds = cursor.fetchall()
        
    st.markdown("### Connected Accounts")
    if not all_creds:
        st.write("No email accounts connected yet.")
    
    for cred in all_creds:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 3, 3, 1])
            with col1:
                st.write(f"**Alias:** {cred['alias']}")
            with col2:
                st.write(f"**Email:** {cred['email_address']}")
            with col3:
                st.write(f"**IMAP:** {cred['imap_server']}:{cred['imap_port']}")
            with col4:
                if st.button("Delete", key=f"del_{cred['id']}", type="primary"):
                    with get_db_connection() as conn:
                        conn.cursor().execute("DELETE FROM email_credentials WHERE id=?", (cred['id'],))
                        conn.commit()
                    st.rerun()
        st.divider()
        
    st.markdown("### Add New Account")
    with st.form("new_email_form"):
        col_new1, col_new2, col_new3 = st.columns(3)
        with col_new1:
            new_alias = st.text_input("Alias Name (e.g. Main, Startup)")
        with col_new2:
            new_email = st.text_input("Email Address")
        with col_new3:
            new_pass = st.text_input("App Password", type="password")
            
        col_new4, col_new5 = st.columns(2)
        with col_new4:
            new_server = st.text_input("IMAP Server", value="imap.gmail.com")
        with col_new5:
            new_port = st.number_input("IMAP Port", value=993)
            
        if st.form_submit_button("Add Email Account"):
            if new_email and new_pass and new_alias:
                with get_db_connection() as conn:
                    conn.cursor().execute(
                        "INSERT INTO email_credentials (imap_server, imap_port, alias, email_address, app_password) VALUES (?, ?, ?, ?, ?)",
                        (new_server, new_port, new_alias, new_email, new_pass)
                    )
                    conn.commit()
                st.success(f"Account '{new_alias}' added!")
                st.rerun()
            else:
                st.error("Please fill in Alias, Email, and Password.")

# --- Scan Button ---
if st.button("🔄 Scan Inbox for Updates Now", type="primary"):
    import subprocess
    import json
    
    st.info("Scanner initialized. DO NOT close this tab. Logs will stream below.")
    log_container = st.empty()
    logs = ""
    
    import os
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.Popen(
        [sys.executable, "-u", "src/agent/email_parser.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding='utf-8',
        errors='replace',
        env=env
    )
    
    final_res = None
    while True:
        line = process.stdout.readline()
        if not line and process.poll() is not None:
            break
        if line:
            if line.startswith("###FINAL_RESULT###"):
                try:
                    final_res = json.loads(line.replace("###FINAL_RESULT###", "").strip())
                except:
                    pass
            else:
                logs += line
                log_container.code(logs[-10000:], language="bash")
                
    if final_res:
        if final_res.get("success"):
            st.success(f"Scan complete! Processed {final_res.get('processed', 0)} relevant emails. Made {final_res.get('updates', 0)} status updates.")
        else:
            st.error(final_res.get("message", "Unknown error"))
    else:
        st.error("Scanner crashed or did not return a valid result.")

st.divider()

# --- Kanban Board ---
with get_db_connection() as conn:
    df = pd.read_sql_query("SELECT * FROM job_applications WHERE status NOT IN ('scraped', 'matched', 'pending_approval', 'skipped') AND email_alias IS NOT NULL", conn)

if df.empty:
    st.info("No active applications found. Start applying in the Job Aggregator first!")
else:
    st.subheader("📋 Active Applications")
    
    # Filter Toggles
    # Make sure we don't crash if 'email_alias' column doesn't exist yet for some reason
    if 'email_alias' not in df.columns:
        df['email_alias'] = None
        
    actual_aliases = [a for a in df['email_alias'].unique() if pd.notna(a)]
    unique_aliases = ["All"] + actual_aliases
    selected_alias = st.selectbox("Filter by Email Alias:", unique_aliases, index=0)
    
    if selected_alias != "All":
        df = df[df['email_alias'] == selected_alias]
    
    st.write("") # Spacer

    col_applied, col_test, col_interview, col_closed = st.columns(4)
    
    def render_card(row, color_hex, border_hex):
        logs_str = str(row['logs']) if pd.notna(row['logs']) else ''
        logs_display = logs_str[:120] + '...' if len(logs_str) > 120 else logs_str
        platform_str = str(row['platform']).capitalize() if pd.notna(row['platform']) else 'Unknown'
        
        if pd.notna(row['email_alias']):
            alias_badge = f"<span style='background:rgba(0,0,0,0.85); color:#fff; padding:3px 8px; border-radius:12px; font-size:0.7em; font-weight:600; letter-spacing:0.5px;'>📧 {row['email_alias']}</span>"
        else:
            alias_badge = ""
        
        html_card = f"""<div style="background-color: {color_hex}; color: #1a1a1a; padding: 18px; border-radius: 12px; margin-bottom: 16px; border: 1px solid {border_hex}; border-top: 4px solid {border_hex}; box-shadow: 0 4px 6px rgba(0,0,0,0.05), 0 1px 3px rgba(0,0,0,0.1);">
<div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 8px;">
<h4 style="margin-top: 0; margin-bottom: 8px; color: #111; font-weight: 700; line-height: 1.2;">{row['company']}</h4>
<div style="flex-shrink: 0; margin-top: 2px;">{alias_badge}</div>
</div>
<div style="font-size: 0.95em; font-weight: 600; color: #333; margin-bottom: 8px;">{row['job_title']}</div>
<div style="display: flex; align-items: center; gap: 6px; margin-bottom: 12px;">
<span style="font-size: 0.75em; font-weight: 600; color: #555; background: rgba(0,0,0,0.06); padding: 4px 8px; border-radius: 6px; text-transform: uppercase;">{platform_str}</span>
</div>
<div style="font-size: 0.85em; color: #444; background: rgba(255,255,255,0.6); padding: 10px; border-radius: 6px; border-left: 3px solid {border_hex}; line-height: 1.4;"><i>{logs_display}</i></div>
</div>"""
        
        st.markdown(html_card, unsafe_allow_html=True)

    with col_applied:
        st.subheader("📬 Applied")
        applied_df = df[df['status'].isin(['applied', 'failed'])]
        for _, row in applied_df.iterrows():
            render_card(row, "#f8f9fa" if row['status'] == 'applied' else "#fff0f0", "#adb5bd" if row['status'] == 'applied' else "#ff8787")

    with col_test:
        st.subheader("📝 Assessment")
        test_df = df[df['status'] == 'assessment']
        for _, row in test_df.iterrows():
            render_card(row, "#f1f8ff", "#74c0fc")

    with col_interview:
        st.subheader("🗣️ Interview")
        int_df = df[df['status'] == 'interview_invite']
        for _, row in int_df.iterrows():
            render_card(row, "#f4fce3", "#8ce99a")

    with col_closed:
        st.subheader("🏁 Closed")
        closed_df = df[df['status'].isin(['rejected', 'offer'])]
        for _, row in closed_df.iterrows():
            render_card(row, "#fff0f0" if row['status'] == 'rejected' else "#fff9db", "#ff8787" if row['status'] == 'rejected' else "#fcc419")

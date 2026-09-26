import streamlit as st
import sqlite3
import subprocess
import sys
import os
import json

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.core.db import get_db_connection
from src.scrapers.linkedin_scraper import scrape_linkedin_jobs
import asyncio

st.set_page_config(page_title="AI Job Aggregator", page_icon="🎯", layout="wide")

st.title("🎯 AI Job Aggregator (Tinder for Jobs)")
st.markdown("Review the jobs sourced and filtered by your AI Agent. Check the ones you want, and launch the bulk application engine.")

# ── Load Preferences ──────────────────────────────────────────────────────────
PREFS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "sourcing_prefs.json")
PLATFORM_PREFS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "platform_prefs.json")

def load_prefs():
    if os.path.exists(PREFS_FILE):
        try:
            with open(PREFS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"roles": "", "location": "India", "max_jobs": 10, "match_threshold": 80}

def load_platform_prefs():
    if os.path.exists(PLATFORM_PREFS_FILE):
        try:
            with open(PLATFORM_PREFS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    return {"linkedin": True}  # Default: LinkedIn only

prefs = load_prefs()
platform_prefs = load_platform_prefs()
enabled_platforms = [k for k, v in platform_prefs.items() if v]

with st.expander("🚀 AI Sourcing Engine Control Panel", expanded=True):
    # Show which platforms are active
    if enabled_platforms:
        st.success(f"**Active Platforms:** {', '.join([p.capitalize() for p in enabled_platforms])} — [Change in Platform Manager →](/Platforms)")
    else:
        st.error("⚠️ No platforms enabled! Go to the **Platforms** page in the sidebar to enable at least one platform.")

    st.markdown("Fetch strictly matched jobs using Headless AI filtering.")
    col_a, col_b = st.columns(2)
    with col_a:
        job_roles_input = st.text_area("Target Job Roles (One per line)", value=prefs.get("roles", ""))
    with col_b:
        loc_options = ["India", "Remote", "Both"]
        current_loc = prefs.get("location", "India")
        if current_loc not in loc_options: current_loc = "India"
        search_location = st.selectbox("Target Location", loc_options, index=loc_options.index(current_loc))
        
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            max_jobs = st.number_input("Max Jobs per role", min_value=10, max_value=200, value=prefs.get("max_jobs", 10), step=10)
        with col_b2:
            threshold_options = [50, 60, 70, 80, 90]
            current_threshold = prefs.get("match_threshold", 80)
            if current_threshold not in threshold_options: current_threshold = 80
            match_threshold = st.selectbox("Min Match %", threshold_options, index=threshold_options.index(current_threshold))
            
        headless_mode = st.toggle("Run in background (Headless Mode)", value=prefs.get("headless", True), help="Turn off to see the browser opening and searching in real time (good for debugging).")
        
    if st.button("💾 Save Settings", type="secondary"):
        new_prefs = {"roles": job_roles_input, "location": search_location, "max_jobs": max_jobs, "match_threshold": match_threshold, "headless": headless_mode}
        with open(PREFS_FILE, "w") as f:
            json.dump(new_prefs, f)
        st.success("Settings saved successfully!")
        st.rerun()
        
    if "search_offset" not in st.session_state:
        st.session_state.search_offset = 0

    import psutil
    import subprocess
    import json
    import os
    import time
    
    pid_file = "logs/aggregator.pid"
    log_file = "logs/aggregator.log"
    
    def is_running(pid):
        try:
            return psutil.pid_exists(pid)
        except:
            return False

    current_pid = None
    if os.path.exists(pid_file):
        try:
            with open(pid_file, "r") as f:
                current_pid = int(f.read().strip())
        except:
            pass

    running = False
    if current_pid and is_running(current_pid):
        running = True
        
    colA, colB = st.columns(2)
    with colA:
        if not running:
            if st.button("Fetch High-Match Jobs (or Load More)", type="primary"):
                roles_list = [r.strip() for r in job_roles_input.split('\n') if r.strip()]
                if not roles_list:
                    st.error("Please enter at least one job role.")
                elif not enabled_platforms:
                    st.error("No platforms enabled! Go to the Platforms page first.")
                else:
                    config = {
                        "platforms": enabled_platforms,
                        "roles": roles_list,
                        "location": search_location,
                        "start_offset": st.session_state.search_offset,
                        "max_jobs": max_jobs,
                        "match_threshold": match_threshold,
                        "headless": headless_mode
                    }
                    with open("logs/agg_config.json", "w") as f:
                        json.dump(config, f)
                        
                    if os.path.exists(log_file):
                        os.remove(log_file)
                        
                    cmd = [sys.executable, "src/agent/run_aggregator.py", "logs/agg_config.json"]
                    with open(log_file, "w") as out:
                        if sys.platform == "win32":
                            p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, creationflags=subprocess.DETACHED_PROCESS)
                        else:
                            p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
                            
                    with open(pid_file, "w") as f:
                        f.write(str(p.pid))
                        
                    st.session_state.search_offset += max_jobs
                    st.rerun()
        else:
            st.button("Fetching Jobs...", type="primary", disabled=True)
            
    with colB:
        if running:
            if st.button("Stop Fetching Jobs", type="secondary"):
                try:
                    parent = psutil.Process(current_pid)
                    for child in parent.children(recursive=True):
                        child.terminate()
                    parent.terminate()
                except:
                    pass
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                st.rerun()
                
    if running:
        st.info("🔄 Aggregator is running in the background. You can safely switch tabs.")
        terminal = st.empty()
        
        while True:
            # Re-check if still running
            if not is_running(current_pid):
                if os.path.exists(pid_file):
                    os.remove(pid_file)
                st.success("Sourcing Complete!")
                break
                
            try:
                if os.path.exists(log_file):
                    with open(log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        terminal.code("\n".join(lines[-30:]), language="bash")
            except:
                pass
            
            time.sleep(1)

    if st.session_state.search_offset > 0:
        if st.button("Reset Search Pagination", help="Click this if you changed your search keywords and want to start from the top again."):
            st.session_state.search_offset = 0
            st.success("Search offset reset to 0.")
            st.rerun()

st.divider()

# Fetch pending jobs
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE status = 'pending_approval' ORDER BY match_score DESC")
    pending_jobs = cursor.fetchall()

if not pending_jobs:
    st.info("🤖 No pending jobs. Use the AI Sourcing Control Panel above to fetch high-match jobs!")
else:
    st.subheader(f"Pending Review ({len(pending_jobs)} Jobs)")
    
    def toggle_all_jobs(val, jobs):
        for job in jobs:
            st.session_state[f"job_{job['id']}"] = val
            
    col_sa, col_da, _ = st.columns([1, 1, 4])
    with col_sa:
        st.button("☑️ Select All", on_click=toggle_all_jobs, args=(True, pending_jobs), use_container_width=True)
    with col_da:
        st.button("☐ Deselect All", on_click=toggle_all_jobs, args=(False, pending_jobs), use_container_width=True)
    
    with st.form("job_approval_form"):
        # We store the checkbox boolean for each job
        selected_jobs = {}
        
        for job in pending_jobs:
            col1, col2, col3, col4 = st.columns([0.5, 3, 2, 1])
            with col1:
                selected = st.checkbox("", key=f"job_{job['id']}", value=True)
                selected_jobs[job['id']] = selected
            with col2:
                st.markdown(f"**{job['job_title']}** at {job['company']}")
            with col3:
                st.markdown(f"*{job['platform'].capitalize()}* - [View Listing]({job['job_url']})")
            with col4:
                # Color code the match score
                score = job['match_score'] or 0
                color = "green" if score >= 85 else "orange" if score >= 70 else "red"
                st.markdown(f"**<span style='color:{color}'>{score}% Match</span>**", unsafe_allow_html=True)
            
            st.divider()
            
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            approve_submit = st.form_submit_button("Approve Selected & Send to Queue", type="primary")
        with col_btn2:
            reject_submit = st.form_submit_button("Reject Unselected")
            
        if approve_submit:
            approved_ids = [job_id for job_id, is_selected in selected_jobs.items() if is_selected]
            if approved_ids:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    placeholders = ",".join(["?"] * len(approved_ids))
                    cursor.execute(f"UPDATE job_applications SET status = 'approved' WHERE id IN ({placeholders})", approved_ids)
                    conn.commit()
                st.success(f"Successfully approved {len(approved_ids)} jobs! They are ready for execution.")
                st.rerun()
                
        if reject_submit:
            rejected_ids = [job_id for job_id, is_selected in selected_jobs.items() if not is_selected]
            if rejected_ids:
                with get_db_connection() as conn:
                    cursor = conn.cursor()
                    placeholders = ",".join(["?"] * len(rejected_ids))
                    cursor.execute(f"UPDATE job_applications SET status = 'rejected' WHERE id IN ({placeholders})", rejected_ids)
                    conn.commit()
                st.success(f"Rejected {len(rejected_ids)} jobs.")
                st.rerun()

st.divider()
col_queue1, col_queue2 = st.columns([7, 2])
with col_queue1:
    st.subheader("🚀 Approved Jobs Queue (Ready to Launch)")
with col_queue2:
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Clear Job Queue", type="secondary", use_container_width=True):
        with get_db_connection() as conn:
            cur = conn.cursor()
            cur.execute("DELETE FROM job_applications WHERE status = 'approved'")
            conn.commit()
        st.success("Cleared approved jobs.")
        st.rerun()

with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE status = 'approved' ORDER BY match_score DESC")
    approved_jobs = cursor.fetchall()

if not approved_jobs:
    st.write("No approved jobs in the queue yet. Approve some jobs above first!")
else:
    st.markdown(f"**{len(approved_jobs)} job(s) are approved and ready to apply.**")
    for job in approved_jobs:
        score = job['match_score'] or 0
        color = "green" if score >= 85 else "orange" if score >= 70 else "red"
        st.markdown(f"- **{job['job_title']}** at {job['company']} ({job['platform'].capitalize()}) — <span style='color:{color}'>{score}% Match</span>", unsafe_allow_html=True)

    engine_pid_file = "logs/engine.pid"
    engine_log_file = "logs/engine.log"
    
    engine_running = False
    if os.path.exists(engine_pid_file):
        try:
            with open(engine_pid_file, "r") as f:
                epid = int(f.read().strip())
                if is_running(epid):
                    engine_running = True
        except:
            pass
            
    colA, colB, colC, colD = st.columns([1.5, 1, 1, 1.5])
    with colA:
        if not engine_running:
            if st.button("🚀 Launch Execution Engine", type="primary", use_container_width=True):
                if os.path.exists(engine_log_file):
                    os.remove(engine_log_file)
                    
                cmd = [sys.executable, "src/agent/run_engine.py"]
                with open(engine_log_file, "w") as out:
                    if sys.platform == "win32":
                        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, creationflags=subprocess.DETACHED_PROCESS)
                    else:
                        p = subprocess.Popen(cmd, stdout=out, stderr=subprocess.STDOUT, start_new_session=True)
                        
                with open(engine_pid_file, "w") as f:
                    f.write(str(p.pid))
                    
                st.rerun()
        else:
            st.button("Engine Running...", type="primary", disabled=True, use_container_width=True)
            
    with colB:
        if engine_running:
            if st.button("⏹ Stop Engine", use_container_width=True):
                try:
                    with open(engine_pid_file, "r") as f:
                        epid = int(f.read().strip())
                        parent = psutil.Process(epid)
                        for child in parent.children(recursive=True):
                            child.terminate()
                        parent.terminate()
                except:
                    pass
                if os.path.exists(engine_pid_file):
                    os.remove(engine_pid_file)
                st.rerun()
                
    with colC:
        st.button("🔄 Refresh Logs", use_container_width=True)
        
    with colD:
        if st.button("🔙 Send Back to Pre-approved", use_container_width=True):
            with get_db_connection() as conn:
                cur = conn.cursor()
                cur.execute("UPDATE job_applications SET status = 'pending_approval' WHERE status = 'approved'")
                conn.commit()
            st.success("Sent back to pre-approved.")
            st.rerun()

    if engine_running:
        st.warning("Bulk application started in the background! You can safely switch tabs or close the browser.")
        terminal = st.empty()
        while True:
            if not is_running(epid):
                if os.path.exists(engine_pid_file):
                    os.remove(engine_pid_file)
                st.success("Execution Complete!")
                break
            try:
                if os.path.exists(engine_log_file):
                    with open(engine_log_file, "r", encoding="utf-8") as f:
                        lines = f.readlines()
                        terminal.code("\n".join(lines[-30:]), language="bash")
            except:
                pass
            time.sleep(1)
            
st.divider()

# Application History Table
col_hist1, col_hist2 = st.columns([7, 2])
with col_hist1:
    st.subheader("📋 Application History")
with col_hist2:
    st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
    if st.button("🗑️ Clear History", type="secondary", use_container_width=True):
        with get_db_connection() as conn:
            conn.cursor().execute("DELETE FROM job_applications WHERE status IN ('applied', 'failed', 'skipped')")
            conn.commit()
        st.success("History cleared!")
        st.rerun()
with get_db_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM job_applications WHERE status IN ('applied', 'failed', 'skipped') ORDER BY applied_at DESC LIMIT 50")
    history = cursor.fetchall()

if history:
    for job in history:
        status_icon = "✅" if job['status'] == 'applied' else "❌" if job['status'] == 'failed' else "⏭️"
        col_hist_info, col_hist_btn = st.columns([5, 1])
        with col_hist_info:
            st.markdown(f"{status_icon} **[{job['job_title']}]({job['job_url']})** at {job['company']} ({job['platform'].capitalize()}) — *{job['status'].capitalize()}*")
        with col_hist_btn:
            if job['status'] == 'failed':
                if st.button("Retry", key=f"retry_{job['id']}", use_container_width=True):
                    with get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE job_applications SET status='pending_approval' WHERE id=?", (job['id'],))
                        conn.commit()
                    st.success("Moved back to Pending!")
                    st.rerun()
            elif job['status'] == 'applied':
                st.link_button("Check", job['job_url'], use_container_width=True)
else:
    st.write("No application history yet. Launch the execution engine to start applying!")


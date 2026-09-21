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
        
    if st.button("💾 Save Settings", type="secondary"):
        new_prefs = {"roles": job_roles_input, "location": search_location, "max_jobs": max_jobs, "match_threshold": match_threshold}
        with open(PREFS_FILE, "w") as f:
            json.dump(new_prefs, f)
        st.success("Settings saved successfully!")
        st.rerun()
        
    if "search_offset" not in st.session_state:
        st.session_state.search_offset = 0

    if st.button("Fetch High-Match Jobs (or Load More)", type="primary"):
        roles_list = [r.strip() for r in job_roles_input.split('\n') if r.strip()]
        if not roles_list:
            st.error("Please enter at least one job role.")
        elif not enabled_platforms:
            st.error("No platforms enabled! Go to the Platforms page first.")
        else:
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            def update_progress(msg, pct):
                status_text.text(msg)
                progress_bar.progress(min(100, max(0, pct)))
            
            # Run scraper for each enabled platform that has a built runner
            for platform in enabled_platforms:
                if platform == "linkedin":
                    status_text.text(f"Starting LinkedIn sourcing...")
                    asyncio.run(scrape_linkedin_jobs(
                        roles_list, search_location,
                        start_offset=st.session_state.search_offset,
                        max_jobs_per_role=max_jobs,
                        match_threshold=match_threshold,
                        progress_callback=update_progress
                    ))
                else:
                    status_text.text(f"⏭️ {platform.capitalize()} scraper coming in Phase 6-B. Skipping...")

            # Increase offset for Load More
            st.session_state.search_offset += max_jobs
            
            st.success("Sourcing complete! Scroll down to review your high-match jobs.")

            st.rerun()

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
st.subheader("🚀 Approved Jobs Queue (Ready to Launch)")

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

    if st.button("🚀 Launch Execution Engine (Bulk Apply)", type="primary"):
        st.warning("Bulk application started! DO NOT close this tab. Logs will stream below.")
        
        overall_progress = st.empty()
        
        for i, job in enumerate(approved_jobs):
            job_id   = job['id']
            job_url  = job['job_url']
            platform = job['platform']
            title    = job['job_title']
            company  = job['company']
            
            overall_progress.markdown(f"### Processing Job {i+1} of {len(approved_jobs)}: **{title}** at {company}")
            
            # Phase 4: Cross-Platform Routing
            # LinkedIn uses hybrid_runner.py. More platforms added in Phase 5.
            if platform == "linkedin":
                cmd = [sys.executable, "src/agent/hybrid_runner.py", "--url", job_url]
            else:
                st.warning(f"Platform '{platform}' not yet supported. Skipping.")
                with get_db_connection() as conn:
                    cur = conn.cursor()
                    cur.execute("UPDATE job_applications SET status='skipped' WHERE id=?", (job_id,))
                    conn.commit()
                continue
            
            # Stream live logs and detect outcome
            with st.spinner(f"Applying to {title}..."):
                try:
                    env = os.environ.copy()
                    env["PYTHONUNBUFFERED"] = "1"
                    env["PYTHONIOENCODING"] = "utf-8"
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        bufsize=1,
                        env=env,
                        cwd=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
                    )
                    
                    log_container = st.empty()
                    logs = ""
                    applied = False
                    
                    for line in iter(process.stdout.readline, ''):
                        logs += line
                        log_container.code(logs[-4000:], language="bash")
                        if "Application submitted successfully" in line:
                            applied = True
                            
                    process.stdout.close()
                    process.wait()
                    
                    # Auto-update database status
                    final_status = "applied" if applied else "failed"
                    with get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute(
                            "UPDATE job_applications SET status=?, applied_at=CURRENT_TIMESTAMP, logs=? WHERE id=?",
                            (final_status, logs[-5000:], job_id)
                        )
                        conn.commit()
                    
                    if applied:
                        st.success(f"Successfully applied to **{title}** at {company}!")
                    else:
                        st.error(f"Failed to apply to **{title}** at {company}. Check logs above.")
                        
                except Exception as e:
                    st.error(f"Error launching agent for {title}: {e}")
                    with get_db_connection() as conn:
                        cur = conn.cursor()
                        cur.execute("UPDATE job_applications SET status='failed' WHERE id=?", (job_id,))
                        conn.commit()
                        
        overall_progress.markdown(f"### All {len(approved_jobs)} jobs processed! Check your application history below.")

st.divider()

# Application History Table
col_hist1, col_hist2 = st.columns([4, 1])
with col_hist1:
    st.subheader("📋 Application History")
with col_hist2:
    if st.button("🗑️ Clear History", type="secondary"):
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
        st.markdown(f"{status_icon} **{job['job_title']}** at {job['company']} ({job['platform'].capitalize()}) — *{job['status'].capitalize()}*")
else:
    st.write("No application history yet. Launch the execution engine to start applying!")


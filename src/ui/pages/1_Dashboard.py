import streamlit as st
import sys
import os
import subprocess
from datetime import datetime, date

# Ensure src is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))
from src.core.db import get_db_connection

st.set_page_config(page_title="Agent Dashboard", page_icon="📊", layout="wide")

st.title("📊 Auto Job Application Dashboard")

# ─────────────────────────────────────────────
# SECTION 1: Live Analytics Metrics from DB
# ─────────────────────────────────────────────

with get_db_connection() as conn:
    cur = conn.cursor()

    # Core counts
    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'applied'")
    total_applied = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'failed'")
    total_failed = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'pending_approval'")
    total_pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'approved'")
    total_approved = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'skipped'")
    total_skipped = cur.fetchone()[0]

    # Today's applications
    cur.execute("SELECT COUNT(*) FROM job_applications WHERE status = 'applied' AND DATE(applied_at) = DATE('now')")
    applied_today = cur.fetchone()[0]

    # Success rate
    total_attempted = total_applied + total_failed
    success_rate = round((total_applied / total_attempted * 100), 1) if total_attempted > 0 else 0

    # Recent applications for history table
    cur.execute("""
        SELECT job_title, company, platform, status, match_score, applied_at, job_url
        FROM job_applications
        WHERE status IN ('applied', 'failed', 'skipped')
        ORDER BY applied_at DESC LIMIT 10
    """)
    recent_apps = cur.fetchall()

    # Top companies applied to
    cur.execute("""
        SELECT company, COUNT(*) as cnt FROM job_applications
        WHERE status = 'applied'
        GROUP BY company ORDER BY cnt DESC LIMIT 5
    """)
    top_companies = cur.fetchall()

    # Platform breakdown
    cur.execute("""
        SELECT platform, COUNT(*) as cnt FROM job_applications
        WHERE status = 'applied'
        GROUP BY platform ORDER BY cnt DESC
    """)
    platform_breakdown = cur.fetchall()

st.markdown("#### Live Application Statistics")
m1, m2, m3, m4, m5, m6, m7 = st.columns(7)
m1.metric("✅ Total Applied",   total_applied)
m2.metric("📅 Applied Today",   applied_today)
m3.metric("📈 Success Rate",    f"{success_rate}%")
m4.metric("❌ Failed",          total_failed)
m5.metric("⏭️ Skipped",        total_skipped)
m6.metric("🕐 Pending Review",  total_pending)
m7.metric("✔️ In Queue",        total_approved)

st.divider()

# ─────────────────────────────────────────────
# SECTION 2: Charts & Breakdowns
# ─────────────────────────────────────────────

col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### 🏆 Top Companies Applied To")
    if top_companies:
        for company, cnt in top_companies:
            st.markdown(f"- **{company}** — {cnt} application(s)")
    else:
        st.info("No applications yet. Launch the Bulk Execution Engine from the Job Aggregator!")

with col_right:
    st.markdown("#### 🌐 Platform Breakdown")
    if platform_breakdown:
        for platform, cnt in platform_breakdown:
            st.markdown(f"- **{platform.capitalize()}** — {cnt} application(s)")
    else:
        st.info("No platform data yet.")

st.divider()

# ─────────────────────────────────────────────
# SECTION 3: Recent Application History
# ─────────────────────────────────────────────

st.markdown("#### 📋 Recent Applications (Last 10)")
if recent_apps:
    header = st.columns([3, 2, 1, 1, 1, 2])
    header[0].markdown("**Job Title**")
    header[1].markdown("**Company**")
    header[2].markdown("**Platform**")
    header[3].markdown("**Status**")
    header[4].markdown("**Match**")
    header[5].markdown("**Applied At**")
    st.divider()
    for app in recent_apps:
        title, company, platform, status, score, applied_at, job_url = app
        status_icon = "✅" if status == "applied" else "❌" if status == "failed" else "⏭️"
        score_str = f"{score}%" if score else "N/A"
        date_str = applied_at[:16] if applied_at else "—"
        row = st.columns([3, 2, 1, 1, 1, 2])
        row[0].markdown(f"**[{title}]({job_url})**")
        row[1].markdown(company)
        row[2].markdown(platform.capitalize())
        row[3].markdown(f"{status_icon} {status.capitalize()}")
        row[4].markdown(score_str)
        row[5].markdown(date_str)
else:
    st.info("No application history yet.")

st.divider()

# ─────────────────────────────────────────────
# SECTION 4: Manual Apply Launcher (preserved)
# ─────────────────────────────────────────────

st.subheader("🚀 Manual Apply Launcher")
st.markdown("Paste individual LinkedIn URLs here to manually trigger the Sniper AI for specific jobs.")
job_urls_input = st.text_area(
    "Enter LinkedIn Job URLs (One per line):",
    placeholder="https://www.linkedin.com/jobs/view/...\nhttps://www.linkedin.com/jobs/view/...",
    height=120
)

mode = st.radio(
    "Select Execution Mode:",
    [
        "Option 1: Smart Hybrid (Free AI Evaluation + Playwright Clicker)",
        "Option 2: Pure Automation (100% Free - No AI Evaluation)",
        "Premium AI Agent (Requires Paid OpenAI/Anthropic API Key)"
    ],
    index=0
)

if st.button("Launch Application Agent", type="primary"):
    urls = [u.strip() for u in job_urls_input.split('\n') if u.strip()]
    if not urls:
        st.error("Please enter at least one valid LinkedIn Job URL.")
    else:
        st.info(f"Starting execution for {len(urls)} job(s). The browser will open in a new window...")
        progress_text = st.empty()

        for i, current_url in enumerate(urls):
            progress_text.markdown(f"### Processing Job {i+1} of {len(urls)}")
            st.write(f"**URL:** {current_url}")

            if "Option 1" in mode:
                cmd = [sys.executable, "src/agent/hybrid_runner.py", "--url", current_url]
            elif "Option 2" in mode:
                cmd = [sys.executable, "src/agent/hybrid_runner.py", "--url", current_url, "--no-ai"]
            else:
                cmd = [sys.executable, "src/agent/runner.py", "--url", current_url]

            with st.spinner(f"Running agent for Job {i+1}..."):
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

                    for line in iter(process.stdout.readline, ''):
                        logs += line
                        log_container.code(logs, language="bash")

                    process.stdout.close()
                    process.wait()

                    if process.returncode == 0:
                        st.success(f"Job {i+1} execution completed successfully!")
                    else:
                        st.error(f"Job {i+1} execution failed. Check the logs above.")

                except Exception as e:
                    st.error(f"Error launching agent for Job {i+1}: {e}")

        progress_text.markdown(f"### 🎉 All {len(urls)} jobs processed!")

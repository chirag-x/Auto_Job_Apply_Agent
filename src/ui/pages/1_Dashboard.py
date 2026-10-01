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

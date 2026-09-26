import streamlit as st
import pandas as pd
import sqlite3
import os
import sys
from datetime import datetime, timedelta
import plotly.express as px

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))
from src.core.db import get_db_connection

st.set_page_config(page_title="Analytics Dashboard", page_icon="📈", layout="wide")

st.title("📈 Application Analytics & Insights")
st.markdown("Track your job search velocity, platform effectiveness, and funnel conversion rates.")

def load_data():
    with get_db_connection() as conn:
        query = "SELECT * FROM job_applications"
        df = pd.read_sql_query(query, conn)
    
    if not df.empty:
        df['applied_at'] = pd.to_datetime(df['applied_at'], errors='coerce')
    return df

df = load_data()

if df.empty:
    st.info("No data available yet. Start scraping and applying to jobs to see analytics!")
    st.stop()

# --- Top Level Metrics ---


total_scraped = len(df)
total_applied = len(df[df['status'].isin(['applied', 'assessment', 'interview_invite', 'rejected', 'offer', 'failed'])])
total_interviews = len(df[df['status'].isin(['interview_invite', 'offer'])])
total_offers = len(df[df['status'] == 'offer'])

# --- Funnel & Platform Analysis ---
col_charts1, col_charts2 = st.columns(2)

plotly_config = {
    'scrollZoom': False,
    'displayModeBar': 'hover'
}

with col_charts1:
    st.subheader("📊 Application Funnel")
    funnel_data = {
        "Stage": ["Applied", "Assessment / Test", "Interview", "Offer"],
        "Count": [
            total_applied,
            len(df[df['status'].isin(['assessment', 'interview_invite', 'offer'])]),
            total_interviews,
            total_offers
        ]
    }
    funnel_df = pd.DataFrame(funnel_data)
    fig_funnel = px.bar(funnel_df, x="Stage", y="Count", color="Stage")
    st.plotly_chart(fig_funnel, use_container_width=True, config=plotly_config)

with col_charts2:
    st.subheader("🎯 Applications by Platform")
    if total_applied > 0:
        applied_df = df[df['status'].isin(['applied', 'assessment', 'interview_invite', 'rejected', 'offer', 'failed'])]
        platform_counts = applied_df['platform'].value_counts().reset_index()
        platform_counts.columns = ['Platform', 'Count']
        fig_platform = px.bar(platform_counts, x="Platform", y="Count", color="Platform")
        st.plotly_chart(fig_platform, use_container_width=True, config=plotly_config)
    else:
        st.write("Not enough data to display.")

st.divider()

# --- Time Series Analysis ---
st.subheader("📅 Application Velocity (Last 30 Days)")
time_df = df.dropna(subset=['applied_at']).copy()

if not time_df.empty:
    cutoff_date = datetime.now() - timedelta(days=30)
    time_df = time_df[time_df['applied_at'] >= cutoff_date]
    
    if not time_df.empty:
        time_df['date'] = time_df['applied_at'].dt.date
        daily_counts = time_df.groupby('date').size().reset_index(name='Applications')
        
        all_dates = pd.date_range(start=cutoff_date.date(), end=datetime.now().date(), freq='D').date
        idx_df = pd.DataFrame({'date': all_dates})
        
        merged_df = pd.merge(idx_df, daily_counts, on='date', how='left').fillna(0)
        
        fig_time = px.line(merged_df, x="date", y="Applications", markers=True)
        st.plotly_chart(fig_time, use_container_width=True, config=plotly_config)
    else:
        st.info("No applications sent in the last 30 days.")
else:
    st.info("No temporal data available yet.")

st.divider()

# --- Detailed Platform Breakdown ---
st.subheader("🏢 Platform Effectiveness")
st.markdown("See which platforms are yielding the most interviews vs rejections.")

if total_applied > 0:
    platforms = df['platform'].unique()
    breakdown_data = []
    
    for p in platforms:
        p_df = df[df['platform'] == p]
        p_applied = len(p_df[p_df['status'].isin(['applied', 'assessment', 'interview_invite', 'rejected', 'offer', 'failed'])])
        p_interviews = len(p_df[p_df['status'].isin(['interview_invite', 'offer'])])
        p_rejected = len(p_df[p_df['status'] == 'rejected'])
        
        if p_applied > 0:
            breakdown_data.append({
                "Platform": p.capitalize(),
                "Applied": p_applied,
                "Interviews": p_interviews,
                "Rejections": p_rejected,
                "Success Rate": f"{(p_interviews / p_applied * 100):.1f}%" if p_applied > 0 else "0%"
            })
            
    if breakdown_data:
        breakdown_df = pd.DataFrame(breakdown_data)
        st.dataframe(breakdown_df, use_container_width=True)
    else:
        st.write("No platform data to display.")

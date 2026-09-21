import streamlit as st
import json
import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..')))

st.set_page_config(page_title="Platforms", page_icon="🌐", layout="wide")

st.title("🌐 Platform Manager")
st.markdown("Select which job platforms the AI Sourcing Engine and Bulk Execution Engine should use. Only **Active** platforms have a working Sniper AI runner. **Coming Soon** platforms are in development.")

PLATFORM_PREFS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "platform_prefs.json"
)

def load_platform_prefs():
    if os.path.exists(PLATFORM_PREFS_FILE):
        try:
            with open(PLATFORM_PREFS_FILE, "r") as f:
                return json.load(f)
        except:
            pass
    # Default: only LinkedIn enabled
    return {"linkedin": True}

def save_platform_prefs(prefs):
    with open(PLATFORM_PREFS_FILE, "w") as f:
        json.dump(prefs, f)

prefs = load_platform_prefs()

# ── Platform Definitions ─────────────────────────────────────────────────────
PLATFORMS = [
    # Tier 1 — Indian Market
    {
        "key": "linkedin",
        "name": "LinkedIn",
        "icon": "🔵",
        "category": "🇮🇳 Indian + Global",
        "description": "World's largest professional network. Easy Apply filter supported.",
        "status": "active",
    },
    {
        "key": "naukri",
        "name": "Naukri.com",
        "icon": "🟠",
        "category": "🇮🇳 Indian + Global",
        "description": "#1 job portal in India. Millions of tech and non-tech listings.",
        "status": "coming_soon",
    },
    {
        "key": "internshala",
        "name": "Internshala",
        "icon": "🟢",
        "category": "🇮🇳 Indian + Global",
        "description": "Best platform for internships and entry-level/fresher jobs in India.",
        "status": "coming_soon",
    },
    {
        "key": "shine",
        "name": "Shine.com",
        "icon": "🔶",
        "category": "🇮🇳 Indian + Global",
        "description": "Major Indian job board with large tech and management listings.",
        "status": "coming_soon",
    },
    {
        "key": "timesjobs",
        "name": "TimesJobs",
        "icon": "🔷",
        "category": "🇮🇳 Indian + Global",
        "description": "Part of Times Group. Strong presence in Indian corporate hiring.",
        "status": "coming_soon",
    },
    {
        "key": "hirist",
        "name": "Hirist.tech",
        "icon": "⚡",
        "category": "🇮🇳 Indian + Global",
        "description": "Exclusively for tech professionals in India. Very targeted listings.",
        "status": "coming_soon",
    },
    {
        "key": "freshersworld",
        "name": "Freshersworld",
        "icon": "🌱",
        "category": "🇮🇳 Indian + Global",
        "description": "India's top platform specifically for freshers and entry-level candidates.",
        "status": "coming_soon",
    },
    # Tier 2 — Global/Startup
    {
        "key": "wellfound",
        "name": "Wellfound (AngelList)",
        "icon": "🚀",
        "category": "🌍 Global / Startup",
        "description": "The #1 platform for startup jobs worldwide. Equity + salary transparency.",
        "status": "coming_soon",
    },
    {
        "key": "indeed",
        "name": "Indeed",
        "icon": "🌐",
        "category": "🌍 Global / Startup",
        "description": "Largest job board globally. 'Indeed Apply' is their Easy Apply equivalent.",
        "status": "coming_soon",
    },
    {
        "key": "glassdoor",
        "name": "Glassdoor",
        "icon": "🪟",
        "category": "🌍 Global / Startup",
        "description": "Good listings with company reviews. Redirects to company ATS on apply.",
        "status": "coming_soon",
    },
    {
        "key": "otta",
        "name": "Otta.com",
        "icon": "✨",
        "category": "🌍 Global / Startup",
        "description": "Curated high-quality tech jobs from top startups and scaleups.",
        "status": "coming_soon",
    },
    {
        "key": "remotive",
        "name": "Remotive.com",
        "icon": "🏠",
        "category": "🌍 Global / Startup",
        "description": "Best platform for remote-only jobs globally. Perfect for Work Preference: Remote.",
        "status": "coming_soon",
    },
]

# ── Render by Category ────────────────────────────────────────────────────────
new_prefs = {}
categories = list(dict.fromkeys(p["category"] for p in PLATFORMS))

with st.form("platform_form"):
    for category in categories:
        st.subheader(category)
        cat_platforms = [p for p in PLATFORMS if p["category"] == category]
        
        cols = st.columns(3)
        for idx, platform in enumerate(cat_platforms):
            col = cols[idx % 3]
            with col:
                is_active    = platform["status"] == "active"
                is_selected  = prefs.get(platform["key"], False)
                
                badge = "✅ Active" if is_active else "🔜 Coming Soon"
                badge_color = "green" if is_active else "gray"
                
                st.markdown(
                    f"**{platform['icon']} {platform['name']}** &nbsp; "
                    f"<span style='color:{badge_color}; font-size:12px'>{badge}</span>",
                    unsafe_allow_html=True
                )
                st.caption(platform["description"])
                
                if is_active:
                    enabled = st.checkbox("Enable this platform", value=is_selected, key=f"chk_{platform['key']}")
                else:
                    st.caption("🔒 Runner not yet built — coming in Phase 6-B")
                    enabled = False  # Force disabled until runner is built
                    
                new_prefs[platform["key"]] = enabled
                st.markdown("---")
        
    submitted = st.form_submit_button("💾 Save Platform Preferences", type="primary")
    if submitted:
        save_platform_prefs(new_prefs)
        enabled_list = [k for k, v in new_prefs.items() if v]
        st.success(f"Saved! Active platforms: **{', '.join(enabled_list) if enabled_list else 'None'}**")
        st.rerun()

# ── Current Status Summary ─────────────────────────────────────────────────────
st.divider()
st.subheader("📊 Current Selection Summary")
enabled_platforms = [p for p in PLATFORMS if prefs.get(p["key"])]
disabled_platforms = [p for p in PLATFORMS if not prefs.get(p["key"]) and p["status"] == "active"]

if enabled_platforms:
    st.success(f"**{len(enabled_platforms)} platform(s) active:** " + ", ".join([f"{p['icon']} {p['name']}" for p in enabled_platforms]))
else:
    st.warning("⚠️ No platforms enabled! The Job Aggregator will not source any jobs.")

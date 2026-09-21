# Aoto Job Agent: Master Roadmap (Phases 1-5)

This document outlines the architectural roadmap for transforming the Aoto Job Agent from a simple Auto-Applier into a Full-Scale AI Recruitment Agency (Sourcing + AI Filtering + UI Approval + Cross-Platform Execution).

## Phase 1: The Database & UI Foundation (Tinder for Jobs)
**Status:** In Progress
*   **Goal:** Build the infrastructure to store scraped jobs and a UI to review them.
*   **Features:**
    *   Initialize `job_applications` table in SQLite (Title, Platform, URL, Status, Match Score).
    *   Create `3_Applications.py` in the Streamlit Dashboard.
    *   **Checkbox UI:** Display jobs fetched from the aggregator with a checkbox for user approval.
    *   "Launch Approved" button to trigger the execution engine on checked jobs.

## Phase 2: The Session & Cookie Manager UI
**Status:** Pending
*   **Goal:** Allow the agent to run completely headless and invisible in the background without needing a debug browser open.
*   **Features:**
    *   Create a secure vault in the Streamlit UI for users to paste their `li_at` (LinkedIn), Naukri, and Wellfound session cookies.
    *   Playwright dynamically loads these cookies, meaning zero manual logins are required.

## Phase 3: The AI Sourcing Engine (Automatic Fetching)
**Status:** Pending
*   **Goal:** Automatically fetch jobs that are strictly compatible with the user's profile.
*   **Features:**
    *   **Silent Background Scraper:** Navigates search pages on LinkedIn, Wellfound, Naukri, etc., scraping titles, URLs, and Job Descriptions.
    *   **AI Filter:** Feeds the Job Description and the User's Max-Level Profile into Groq. Groq calculates a compatibility score (e.g., 85%).
    *   If the score is high enough, the job is saved to the SQLite DB with the status `pending_approval`, causing it to instantly appear in the Checkbox UI from Phase 1.

## Phase 4: Cross-Platform Domination (Wellfound, Naukri, Indeed)
**Status:** Pending
*   **Goal:** Execute the approved jobs across multiple ATS platforms simultaneously.
*   **Features:**
    *   Modular Runner Architecture: Read the URL (e.g., `wellfound.com/jobs/123`).
    *   Route to the appropriate Sniper AI runner (e.g., `Wellfound_Runner.py`, `Naukri_Runner.py`).
    *   Exhaust the daily application budgets across all 5 major platforms effortlessly.

## Phase 5: The Vision AI Fallback (The Ultimate Safety Net)
**Status:** Pending
*   **Goal:** Ensure 100% execution rate even if a platform entirely changes its underlying HTML code.
*   **Features:**
    *   If the Native DOM (Playwright) Reflection Loop fails twice, Playwright captures a full-screen screenshot.
    *   The screenshot is sent to a Multimodal Vision AI (Groq Llama 3.2 Vision or Gemini Pro Vision).
    *   The AI calculates the X/Y coordinates of the required text boxes/buttons, and Playwright manually clicks the physical pixels on the screen.

## Phase 6 & Beyond (Future Architectural Ideas)
*   **Automated Email Parsing:** Connect the agent to Gmail/Outlook via IMAP. The AI reads incoming emails to detect interview invitations or rejection letters, updating the SQLite Database accordingly.
*   **Auto-Scheduling:** If an interview invite contains a Calendly link or asks for availability, the AI cross-references the user's Google Calendar and automatically replies to the recruiter to book the slot.
*   **Analytics Dashboard:** A beautiful graphical dashboard showing Application Success Rate, Platform Conversion Rate, and Top Skills requested by recruiters.

# Unplanned Architectural Changes & Additions

This document tracks all features, architectural shifts, and fixes implemented during development that were not originally specified in the project's foundational documentation (`PRD.md`, `ARCHITECTURE.md`, `TASKS.md`).

## 1. Three-Tier Execution Architecture
The original architecture relied entirely on `browser-use` for automation. However, testing revealed that `browser-use` requires transferring massive DOM accessibility trees that exceed the context windows and Rate Limits of free-tier LLM providers (like Groq). 

To resolve this, we introduced a 3-Tier Execution Mode:
- **Premium Agent (browser-use)**: For users with paid OpenAI/Anthropic API keys, retaining full autonomous capability.
- **Smart Hybrid (Option 1)**: Uses a custom Playwright script (`hybrid_runner.py`) to extract only the job description, sends it to a free-tier LLM (e.g., Groq) for evaluation and cover letter generation, and automates the application clicks manually.
- **Pure Automation (Option 2)**: Uses the `--no-ai` flag to entirely skip LLM evaluation, functioning as a 100% free auto-clicker for standard Easy Apply jobs.

## 2. Advanced React UI Bypasses
To make `hybrid_runner.py` robust against LinkedIn's complex React frontend, several advanced scraping techniques were introduced:
- **CDP Mouse Events**: Bypassed React's synthetic event swallowing by extracting Javascript element handles and dispatching hardware-level Chrome DevTools Protocol (`.click(force=True)`) mouse events.
- **Defeating Virtualized Scrolling**: LinkedIn uses virtualized DOMs where off-screen elements are deleted. We implemented a raw mouse-wheel injection (`page.mouse.wheel()`) to forcefully scroll modals and force React to render hidden elements (like the 'Submit application' button).
- **Tag-Agnostic Locators**: Removed reliance on `<button>` tags, transitioning to pure Playwright case-insensitive text locators (`text=/.../i`) to catch `<span>` or `<div>` elements acting as custom buttons.

## 3. "Smart Pause" Human-in-the-Loop Workflow
Because the Hybrid and Pure Automation modes rely on hardcoded Playwright scripts rather than a full DOM-reading AI, they cannot inherently answer custom company questions (e.g., "Are you comfortable with onsite interviews?"). 
- We introduced a "Smart Pause" mechanism that detects form validation errors (`.artdeco-inline-feedback--error`).
- When an error is detected, the script pauses indefinitely, alerts the user in the UI to answer the custom question, and resumes instantly upon detecting a successful manual click of the 'Next' button.

## 4. Subprocess Streaming UI
Updated `1_Dashboard.py` from a static placeholder into a live task launcher. It spawns the agent in a background process using `subprocess.Popen` and uses `PYTHONUNBUFFERED=1` to stream real-time execution logs directly into a Streamlit code block.

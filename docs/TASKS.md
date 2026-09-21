# Tasks

## Phase 1: Environment & Architecture Setup
- [ ] Initialize Python 3.11.9 virtual environment with `streamlit`, `litellm`, `browser-use`, `playwright`, `pypdf`.
- [ ] Implement `src/core/db.py` to support `user_profile`, `llm_config`, and `job_applications` tables.
- [ ] Build `src/core/resume_parser.py` to extract raw text and structured data from PDFs.

## Phase 2: Settings & Profile UI
- [ ] Create `src/ui/pages/3_Settings.py` with dynamic provider fields (API key, model, URL) and fallback order.
- [ ] Build `src/ui/pages/2_Profile.py` with resume upload and dynamic personal info forms.
- [ ] Implement secure local storage of user configuration in SQLite.

## Phase 3: Multi-Model Routing & Failover
- [ ] Implement `src/agent/llm_gateway.py` reading dynamic configurations from the database.
- [ ] Add support for Ollama, Gemini Free API, OpenRouter, and OmniRoute endpoints.
- [ ] Write fallback tests: verify automatic failover when Model 1 is unreachable.

## Phase 4: Browser Automation & Integration
- [ ] Create interactive session recorder page in the UI for one-time LinkedIn/Naukri logins.
- [ ] Connect `browser-use` to use dynamic user profile variables during form completion.
- [ ] Build human-in-the-loop review modal in `1_Dashboard.py` before final submission clicks.
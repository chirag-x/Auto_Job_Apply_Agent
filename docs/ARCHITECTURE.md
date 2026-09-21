# Architecture

## 1. System Components
- **Language:** Python 3.13.15
- **User Interface:** Streamlit (pure Python, zero-configuration local Web UI)
- **Browser Automation:** `browser-use` running on top of `playwright`
- **Multi-Model Routing & Failovers:** `litellm` (Router class) wrapped in LangChain's `ChatLiteLLM`
- **Supported Brain Providers:** Ollama (local), Google AI Studio (Gemini), OpenRouter, OmniRoute
- **Document Parser:** `pypdf` / `pdfplumber` for automated resume text extraction
- **Database & Persistence:** Built-in `sqlite3` (stores user profile, app settings, and applied jobs)

## 2. Dynamic Architecture & Flow
```text
┌─────────────────────────────────────────────────────────────┐
│                    Streamlit Web UI                         │
│  - Settings Tab (API Keys, Endpoints, Model Fallbacks)      │
│  - Profile Tab (Personal info, Work auth, Custom answers)   │
│  - Resume Upload (PDF parsing & skill extraction)           │
│  - Live Monitor & Application Approval Modal                │
└──────────────┬───────────────────────────────┬──────────────┘
               │ Save Config / Profile         │ Start Agent Run
               ▼                               ▼
┌──────────────────────────────┐ ┌────────────────────────────┐
│      Local SQLite Store      │ │    Agent Controller Loop   │
│ (config, profile, jobs, logs)│ │ (browser-use + Playwright) │
└──────────────────────────────┘ └─────────────┬──────────────┘
                                               │
                         ┌─────────────────────▼───────────────┐
                         │       LiteLLM Router Client         │
                         │ Priority 1 -> 2 -> 3 -> Fallback   │
                         └─────────────────────────────────────┘
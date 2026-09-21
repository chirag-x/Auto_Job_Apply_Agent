# Design System

## Platform & Theme
- Framework: Streamlit
- Base Palette: Modern Dark Mode (slate background #0F172A, card container #1E293B, primary accent #6366F1, success #10B981, error #EF4444)
- Typography: System default sans-serif (clean, readable)

## UI Navigation & Layout
1. **Dashboard (`1_Dashboard.py`):**
   - Real-time job run metrics (Scraped, Matched, Applied, Skipped).
   - Live browser execution feed and log viewer.
   - Interactive prompt dialog when human approval is required.

2. **Profile & Resume Management (`2_Profile.py`):**
   - Drag-and-drop file uploader accepting `.pdf` and `.docx`.
   - Form fields: Full Name, Email, Phone, Location, Portfolio/GitHub URLs, Years of Experience, Work Authorization.
   - Dynamic custom QA table (e.g., "Do you require sponsorship?", "Expected salary").

3. **Settings & Brain Configuration (`3_Settings.py`):**
   - Provider Selection Cards: Ollama, Gemini, OpenRouter, OmniRoute.
   - Dynamic credential inputs: API Key (password-masked), Endpoint URL, Model Identifier.
   - Reorderable fallback priority list.
   - Maximum daily applications slider (default: 15).

## States
- Empty States: Helpful instructions when no resume is uploaded or no API keys are entered.
- Loading States: Spinners during PDF ingestion and scraping loops.
- Alert States: Visible warning banners if an LLM hits a rate limit or falls back to secondary models.
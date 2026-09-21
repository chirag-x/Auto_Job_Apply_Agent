# Project Memory

## Current Status
System design updated for universal public use with a dynamic Web UI.

## Completed
- Updated documentation suite to eliminate hardcoded personas.
- Selected Streamlit for the frontend and `pypdf` for resume ingestion.
- Designed dynamic configuration schema for Ollama, Gemini, OpenRouter, and OmniRoute with automatic failover.

## Core Capabilities
- Self-hosted, local-first application (100% free operation).
- Dynamic profile and resume ingestion via web interface.
- Resilient web agent powered by `browser-use` and `LiteLLM`.

## Next Step
- Build `src/core/db.py` to set up SQLite tables for user profiles, LLM credentials, and application tracking.
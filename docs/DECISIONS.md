# Architecture Decisions

## ADR-001
Decision: Use `browser-use` and Playwright instead of Selenium or requests.
Reason: Modern job boards use complex React/Angular DOMs that change dynamically. `browser-use` parses accessibility trees natively for LLMs, making automation resilient to UI changes.

## ADR-002
Decision: Use local SQLite instead of PostgreSQL.
Reason: Ensures zero cost for end users and avoids cloud hosting requirements. The database file lives locally on the user's computer.

## ADR-003
Decision: Dynamic User Profile Ingestion over Hardcoded Values.
Reason: The application must support any end user without requiring code modifications. User data and resumes are saved into the local SQLite database and injected into LLM prompts at runtime.

## ADR-004
Decision: Use Streamlit for the application interface.
Reason: Allows rapid deployment of an interactive, local web dashboard in pure Python with built-in support for file uploads, reactive forms, and password-masked settings.
# Security Requirements

## User Data Privacy
- All user details, resumes, and platform cookies must be stored strictly on the local machine (`localhost`).
- No telemetry or application data may be sent to third-party tracking servers.

## Credential & API Key Protection
- API keys entered via the UI must be masked and stored locally in the SQLite database or `.env`.
- Platform login passwords must never be stored in plain text; the agent relies entirely on exported browser session cookies (`storageState.json`).

## File Upload Validation
- Restrict resume uploads strictly to `.pdf` and `.docx` formats[cite: 1].
- Enforce a maximum file upload size of 10 MB to prevent local memory exhaustion[cite: 1].
- Sanitize uploaded filenames before writing them to disk[cite: 1].

## Platform Safety (Anti-Ban)
- Limit automated applications to a safe daily ceiling (user-configurable, default: 15).
- Maintain human-like random jitter (3–8 second delays) between actions.
- Never run automation completely headless during initial authentication.
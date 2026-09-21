# Development Rules

## General
- Use Python 3.11 type hinting strictly.
- Keep functions small and modular to minimize token usage for the LLM.
- Database operations must use SQLite `sqlite3` built-in library; do not install heavy ORMs unless necessary.

## Automation & AI
- Never use hardcoded `time.sleep()`. Rely on Playwright's auto-waiting web-first assertions.
- Optimize prompts to be concise. If using the Gemini Free Tier, stay strictly under the 15 Requests Per Minute (RPM) limit by implementing a rate-limiter queue.
- If using Ollama, ensure tool schemas are strictly defined to prevent hallucinated function calls.

## Security
- Never expose platform passwords in the source code.
- Validate LLM JSON outputs before executing Playwright clicks.
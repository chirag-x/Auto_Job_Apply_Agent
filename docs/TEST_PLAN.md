# Test Plan

## Authentication & State
- Verify Playwright `storageState` correctly bypasses the LinkedIn login screen without triggering CAPTCHAs.
- Verify session cookies persist between script executions.

## Scraping & Deduplication
- Agent successfully parses 10 job listings from a search URL.
- SQLite database rejects duplicate job IDs on subsequent runs.

## LLM Reasoning Engine
- Resume matcher correctly identifies missing skills and outputs a structured JSON score.
- Accessibility tree parser successfully maps semantic HTML (e.g., "First Name Input") to the correct Playwright action.

## End-to-End (E2E) Test
- Agent navigates to an "Easy Apply" job.
- Agent successfully fills out text fields.
- Agent uploads the PDF resume.
- Agent successfully pauses BEFORE clicking the final submit button.
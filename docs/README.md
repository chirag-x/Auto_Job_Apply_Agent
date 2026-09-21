# Auto Job Application Agent

An autonomous, zero-cost AI agent built with Python, Playwright, and `browser-use` to automatically scrape, score, and apply to job listings.

## Setup Instructions
1. Clone the repository.
2. Install Python 3.11.9.
3. Run `pip install -r requirements.txt`.
4. Run `playwright install`.
5. Copy `.env.example` to `.env` and add your local paths and API keys.

## Generating Sessions
Before running the agent, you must manually log into the job platforms to save your session state:
`python src/auth/generate_linkedin_session.py`

## Running the Agent
`python src/main.py --platform linkedin --limit 10`

# To run in devloper mode ?
streamlit run src/ui/app.py
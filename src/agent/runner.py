import asyncio
import os
import sys
import json

# Ensure the root project directory is in the python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from browser_use import Agent
from playwright.async_api import async_playwright
from src.agent.langchain_llm import get_browser_use_llm
from src.core.crud import get_user_profile

STATE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storageState.json")

async def run_job_application(job_url: str):
    print(f"Starting job application for: {job_url}")
    
    # 1. Check for session
    if not os.path.exists(STATE_FILE):
        raise FileNotFoundError("storageState.json not found. Please log in using the Session Manager UI first.")
        
    # 2. Get LLM and User Profile
    llm = get_browser_use_llm()
    profile = get_user_profile()
    
    if not profile:
        raise ValueError("User profile is empty. Please fill it out in the Profile UI.")
        
    # Build a context string from the profile to feed to the agent
    profile_context = f"""
    You are applying for a job on behalf of the user. 
    Use the following exact details when filling out any application forms. 
    Do NOT invent information. If a required field is not in this list, do your best to infer from the resume or leave it blank.
    
    Full Name: {profile.get('full_name')}
    Email: {profile.get('email')}
    Phone: {profile.get('phone')}
    Location: {profile.get('location')}
    Portfolio/LinkedIn: {profile.get('portfolio_url')}
    GitHub: {profile.get('github_url')}
    Years of Experience: {profile.get('years_experience')}
    Work Authorization: {profile.get('work_authorization')}
    
    Custom Q&A Overrides:
    {profile.get('custom_qa', 'None')}
    
    Parsed Resume Data:
    {profile.get('resume_parsed_data', 'None')}
    """

    task_prompt = f"""
    Navigate to this job posting: {job_url}
    1. Click the "Easy Apply" or "Apply Now" button.
    2. Fill out all application form fields using the provided user profile details.
    3. If asked to upload a resume, note that this must be handled manually or by a specific file picker action.
    4. Proceed through all steps of the application.
    5. CRITICAL: Stop at the final "Review" or "Submit Application" screen. Do NOT click the final submit button.
    
    User Profile Details:
    {profile_context}
    """

    print("Initializing Playwright and browser-use Agent...")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=['--disable-blink-features=AutomationControlled'],
            ignore_default_args=["--enable-automation"]
        )
        context = await browser.new_context(storage_state=STATE_FILE)
        
        agent = Agent(
            task=task_prompt,
            llm=llm,
            browser_context=context,
            use_vision=False
        )
        
        print("Agent is now executing the task...")
        result = await agent.run()
        print("Agent finished execution.")
        print(result)
        
        # Keep browser open for the user to review the final submission (Human-in-the-loop)
        print("Waiting for human review... (Close the browser window when done)")
        pages = context.pages
        if pages:
            try:
                await pages[0].wait_for_event("close", timeout=0)
            except Exception:
                pass
                
        await browser.close()
        return result

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="URL of the job posting")
    args = parser.parse_args()
    
    asyncio.run(run_job_application(args.url))

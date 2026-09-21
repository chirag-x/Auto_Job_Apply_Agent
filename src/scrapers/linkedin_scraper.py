import asyncio
import os
import urllib.parse
import json
import sqlite3
from playwright.async_api import async_playwright

# Ensure src is in the python path
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.crud import get_all_llm_configs, get_user_profile
from src.core.db import get_db_connection
from langchain_openai import ChatOpenAI

async def scrape_linkedin_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None):
    """
    Scrapes LinkedIn jobs based on roles and location.
    Uses native Easy Apply filters.
    Evaluates each job via Groq/Active LLM.
    Saves >= match_threshold% matches to DB.
    """
    state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storageState.json")
    if not os.path.exists(state_file):
        if progress_callback: progress_callback("Error: storageState.json not found! Please login via Session Manager first.", 0)
        return

    # 1. Setup LLM
    configs = get_all_llm_configs()
    active_configs = [c for c in configs if c.get('is_active') and c.get('api_key')]
    if not active_configs:
        if progress_callback: progress_callback("Error: No active LLM config with an API Key found in Settings.", 0)
        return
        
    best = active_configs[0]
    llm = ChatOpenAI(
        model=best['model_name'],
        api_key=best['api_key'],
        base_url="https://api.groq.com/openai/v1" if best['provider'] == 'groq' else None,
        temperature=0.0
    )
    
    profile = get_user_profile() or {}
    profile_json = json.dumps(profile)

    if progress_callback: progress_callback("Launching Headless Browser...", 5)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()
        
        total_roles = len(roles)
        
        for role_idx, role in enumerate(roles):
            role = role.strip()
            if not role: continue
            
            jobs_processed = 0
            current_start = start_offset
            
            while jobs_processed < max_jobs_per_role:
                query = urllib.parse.quote(role)
                loc = urllib.parse.quote(location)
                url = f"https://www.linkedin.com/jobs/search/?keywords={query}&location={loc}&f_AL=true&start={current_start}"
                
                if progress_callback: progress_callback(f"Role {role_idx+1}/{total_roles}: Searching '{role}' (Batch {current_start//25 + 1})...", 10)
                
                await page.goto(url)
                await page.wait_for_timeout(3000)
                
                # Check for "No matching jobs"
                if await page.locator("h1:has-text('No matching jobs')").count() > 0:
                    break
                
                job_cards = await page.locator(".job-card-container").all()
                if not job_cards:
                    break # No more jobs
                
                # We need to scroll the left pane to load all 25 jobs
                left_pane = page.locator(".jobs-search-results-list")
                if await left_pane.count() > 0:
                    await left_pane.first.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                    await page.wait_for_timeout(1000)
                    job_cards = await page.locator(".job-card-container").all()
                
                for card_idx, card in enumerate(job_cards):
                    if jobs_processed >= max_jobs_per_role:
                        break
                        
                    try:
                        # Scroll card into view and click
                        await card.scroll_into_view_if_needed()
                        await card.click()
                        await page.wait_for_timeout(1500)
                        
                        # Extract data
                        job_title = await page.locator(".job-details-jobs-unified-top-card__job-title").first.inner_text()
                        company = await page.locator(".job-details-jobs-unified-top-card__company-name").first.inner_text()
                        
                        a_tag = card.locator("a").first
                        job_url = await a_tag.get_attribute("href")
                        if job_url:
                            job_url = "https://www.linkedin.com" + job_url.split("?")[0]
                            
                        if progress_callback: progress_callback(f"Evaluating: {job_title} at {company}...", 10)
                        
                        # Check DB to prevent re-evaluation of duplicates
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT id FROM job_applications WHERE job_url = ?", (job_url,))
                            if cursor.fetchone():
                                jobs_processed += 1
                                continue # Skip already processed jobs
                                
                        # Extract description
                        desc_element = page.locator(".jobs-description__content")
                        if await desc_element.count() > 0:
                            desc_text = await desc_element.first.inner_text()
                        else:
                            continue
                        
                        # AI Scoring (Truncate description to save context limits)
                        prompt = f"""
                        You are an expert ATS recruiter. Compare this candidate to the job description.
                        
                        Candidate Profile (JSON):
                        {profile_json}
                        
                        Job Title: {job_title}
                        Company: {company}
                        Job Description (Truncated):
                        {desc_text[:4000]}
                        
                        CRITICAL RULE: Evaluate strictly based on the candidate's skills, years of experience, and location compatibility.
                        Output JSON strictly. Format:
                        {{"score": 85, "reason": "Candidate has 3 years of React but lacks AWS."}}
                        """
                        
                        response = await asyncio.to_thread(llm.invoke, prompt)
                        
                        # Parse JSON safely
                        raw_text = response.content.strip()
                        if raw_text.startswith("```json"): raw_text = raw_text[7:]
                        if raw_text.startswith("```"): raw_text = raw_text[3:]
                        if raw_text.endswith("```"): raw_text = raw_text[:-3]
                        
                        result = json.loads(raw_text.strip())
                        score = int(result.get("score", 0))
                        
                        if score >= match_threshold:
                            if progress_callback: progress_callback(f"✅ FOUND MATCH: {job_title} ({score}%)", 10)
                            # Save to Database
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                try:
                                    # Extract Job ID from URL (e.g. view/12345/)
                                    job_id = job_url.split("view/")[1].split("/")[0] if "view/" in job_url else str(hash(job_url))
                                    
                                    cursor.execute("""
                                        INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, ("linkedin", job_id, job_title, company, job_url, "pending_approval", score))
                                    conn.commit()
                                except sqlite3.IntegrityError:
                                    pass # Already exists
                        else:
                            if progress_callback: progress_callback(f"❌ Rejected: {job_title} ({score}%)", 10)
                            
                    except Exception as e:
                        print(f"Error processing job card: {e}")
                        
                    jobs_processed += 1
                
                # Move to next page
                current_start += 25
                if len(job_cards) < 15: # Means we reached the end of the results
                    break
                    
        await browser.close()
        
        if progress_callback: progress_callback("🎉 Scraping and Filtering Complete!", 100)

if __name__ == "__main__":
    # Test script
    asyncio.run(scrape_linkedin_jobs(["Python Developer"], "India", max_jobs_per_role=5))

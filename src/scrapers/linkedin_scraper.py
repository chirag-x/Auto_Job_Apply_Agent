import asyncio
import json
import os
import sqlite3
import sys
import urllib.parse
from playwright.async_api import async_playwright
from src.agent.langchain_llm import build_llm

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from src.core.crud import get_all_llm_configs, get_user_profile
from src.core.db import get_db_connection

async def scrape_linkedin_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None, headless=True):
    profile = get_user_profile()
    if not profile:
        if progress_callback: progress_callback("Error: User profile not found.", 0)
        return
        
    configs = get_all_llm_configs()
    active_configs = [c for c in configs if c.get('is_active')]
    if not active_configs:
        if progress_callback: progress_callback("Error: No active LLM config found.", 0)
        return

    profile_json = json.dumps(profile)
    state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'storageState.json'))
    
    if not os.path.exists(state_file):
        if progress_callback: progress_callback("Error: Please login via Session Manager first.", 0)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
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
                
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await page.wait_for_timeout(3000)
                
                if await page.locator("h1:has-text('No matching jobs')").count() > 0:
                    break
                
                job_cards = await page.locator(".job-card-container").all()
                if not job_cards:
                    break
                
                left_pane = page.locator(".jobs-search-results-list")
                if await left_pane.count() > 0:
                    await left_pane.first.evaluate("el => el.scrollTo(0, el.scrollHeight)")
                    await page.wait_for_timeout(1000)
                    job_cards = await page.locator(".job-card-container").all()
                
                for card_idx, card in enumerate(job_cards):
                    if jobs_processed >= max_jobs_per_role:
                        break
                        
                    try:
                        await card.scroll_into_view_if_needed()
                        await card.click()
                        await page.wait_for_timeout(1500)
                        
                        job_title = await page.locator(".job-details-jobs-unified-top-card__job-title").first.inner_text()
                        company = await page.locator(".job-details-jobs-unified-top-card__company-name").first.inner_text()
                        
                        a_tag = card.locator("a").first
                        job_url = await a_tag.get_attribute("href")
                        if job_url:
                            if "currentJobId=" in job_url:
                                import urllib.parse
                                parsed = urllib.parse.urlparse(job_url)
                                qs = urllib.parse.parse_qs(parsed.query)
                                job_id = qs.get("currentJobId", [""])[0]
                                job_url = f"https://www.linkedin.com/jobs/view/{job_id}/"
                            else:
                                job_url = "https://www.linkedin.com" + job_url.split("?")[0]
                            
                        if progress_callback: progress_callback(f"Evaluating: {job_title} at {company}...", 10)
                        
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
                            cursor.execute("SELECT id FROM job_applications WHERE job_url = ?", (job_url,))
                            if cursor.fetchone():
                                jobs_processed += 1
                                continue
                                
                        desc_element = page.locator(".jobs-description__content")
                        if await desc_element.count() > 0:
                            desc_text = await desc_element.first.inner_text()
                        else:
                            continue
                        
                        prompt = f"""You are an expert ATS recruiter. Compare this candidate to the job description.
                        
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
                        
                        score = None
                        for best in sorted(active_configs, key=lambda x: x.get('priority', 99)):
                            try:
                                llm = build_llm(best, temperature=0.0)
                                response = await asyncio.to_thread(llm.invoke, prompt)
                                raw = response.content.strip().strip("```json").strip("```").strip()
                                result = json.loads(raw)
                                score = int(result.get("score", 0))
                                break
                            except Exception as e:
                                if progress_callback:
                                    progress_callback(f"⚠️ Brain '{best['model_name']}' failed. Trying next...", 10)
                                continue
                                
                        if score is None:
                            if progress_callback: progress_callback(f"❌ All brains failed for {job_title}. Skipping.", 10)
                            continue

                        if score >= match_threshold:
                            if progress_callback: progress_callback(f"✅ FOUND MATCH: {job_title} ({score}%)", 10)
                            with get_db_connection() as conn:
                                cursor = conn.cursor()
                                try:
                                    job_id = job_url.split("view/")[1].split("/")[0] if "view/" in job_url else str(hash(job_url))
                                    cursor.execute("""
                                        INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)
                                        VALUES (?, ?, ?, ?, ?, ?, ?)
                                    """, ("linkedin", job_id, job_title, company, job_url, "pending_approval", score))
                                    conn.commit()
                                except sqlite3.IntegrityError:
                                    pass
                        else:
                            if progress_callback: progress_callback(f"❌ Rejected: {job_title} ({score}%)", 10)
                            
                    except Exception as e:
                        print(f"Error processing job card: {e}")
                        
                    jobs_processed += 1
                
                current_start += 25
                if len(job_cards) < 15:
                    break
                    
        await browser.close()
        if progress_callback: progress_callback("✅ Scraping and Filtering Complete!", 100)

if __name__ == "__main__":
    asyncio.run(scrape_linkedin_jobs(["Python Developer"], "India", max_jobs_per_role=5))

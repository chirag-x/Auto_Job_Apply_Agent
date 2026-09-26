import asyncio

import os

import urllib.parse

import json

import sqlite3

from playwright.async_api import async_playwright



import sys

# Go 3 levels up: src/scrapers/ -> src/ -> project root

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))



from src.core.crud import get_all_llm_configs, get_user_profile

from src.core.db import get_db_connection

from src.agent.langchain_llm import build_llm





async def scrape_wellfound_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None, headless=True):

    """

    Scrapes Wellfound (AngelList Talent) for startup jobs matching given roles.

    Scores each job with Groq and saves >= match_threshold% to the DB.

    """

    state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'storageState_wellfound.json'))



    if not os.path.exists(state_file):

        if progress_callback:

            progress_callback("Error: Wellfound session not found. Please login via Session Manager.", 0)

        return



    configs = get_all_llm_configs()

    active_configs = [c for c in configs if c.get('is_active')]

    if not active_configs:

        if progress_callback:

            progress_callback("Error: No active LLM config. Please add one in Settings.", 0)

        return



    profile = get_user_profile() or {}

    profile_json = json.dumps(profile)



    if progress_callback:

        progress_callback("Wellfound: Launching headless browser...", 5)



    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=headless)

        context = await browser.new_context(

            storage_state=state_file,

            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        )

        page = await context.new_page()



        for role_idx, role in enumerate(roles):

            role = role.strip()

            if not role:

                continue



            jobs_saved = 0

            role_encoded = urllib.parse.quote(role)

            # Wellfound uses "Remote" as a location option natively

            loc = "Remote" if location == "Remote" else "India"



            search_url = f"https://wellfound.com/jobs"

            if progress_callback:
                progress_callback(f"Wellfound [{role_idx+1}/{len(roles)}]: Searching '{role}'...", 10)

            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Check for login wall
                page_text = await page.locator("body").inner_text()
                if "Sign up" in page_text and "Log in" in page_text and "search" not in page_text.lower():
                    if progress_callback:
                        progress_callback("Wellfound: Login wall detected. Please re-login via Session Manager.", 0)
                    await browser.close()
                    return

                # Follow exact UI Traversal: Filters -> Skills -> Type to search -> Enter -> View results
                filters_btn = page.locator("button:has-text('Filters')")
                if await filters_btn.count() > 0:
                    await filters_btn.first.click()
                    await page.wait_for_timeout(2000)
                    
                    # The modal has "Skills" and "Markets" both with "Type to search"
                    # We grab the first one, which is Skills
                    skills_input = page.locator("input[placeholder='Type to search']").first
                    if await skills_input.count() > 0:
                        await skills_input.fill(role)
                        await page.wait_for_timeout(2000)
                        
                        # Use Keyboard navigation to ensure React registers the selection
                        await page.keyboard.press("ArrowDown")
                        await page.wait_for_timeout(500)
                        await page.keyboard.press("Enter")
                        
                        await page.wait_for_timeout(1000)
                        
                    # Click View results
                    view_btn = page.locator("button:has-text('View results'), div:has-text('View results')").last
                    if await view_btn.count() > 0:
                        await view_btn.click(force=True)
                        await page.wait_for_timeout(4000)
                else:
                    # Fallback just in case
                    search_url2 = f"https://wellfound.com/jobs?q={role_encoded}&l={urllib.parse.quote(loc)}"
                    await page.goto(search_url2)
                    await page.wait_for_timeout(5000)

            except Exception as e:
                if progress_callback:
                    progress_callback(f"Wellfound: Failed to load search page: {e}", 10)
                continue

            # Wellfound cards
            cards = await page.locator('[data-test="StartupResult"], div[class*="styles_component__"]').all()
            all_links = []
            if cards:
                for card in cards:
                    links = await card.locator('a[href*="/jobs/"]').all()
                    if links:
                        all_links.extend(links)
            else:
                all_links = await page.locator('a[href*="/jobs/"]').all()



            job_data = []

            seen_urls = set()

            for link in all_links:

                try:

                    href = await link.get_attribute("href") or ""

                    # Filter to actual job detail pages (not search/company pages)

                    if "/jobs/" in href and not any(href.rstrip("/").endswith(x) for x in ["/jobs", "/home", "/messages", "/applied", "/hidden", "/saved"]):

                        full_url = "https://wellfound.com" + href if not href.startswith("http") else href

                        title = (await link.inner_text()).strip()

                        if full_url not in seen_urls and len(title) > 3:

                            job_data.append({"url": full_url, "title": title})

                            seen_urls.add(full_url)

                except:

                    continue



            if not job_data:

                if progress_callback:

                    progress_callback(f"Wellfound: No job links found for '{role}'. Wellfound may require login.", 10)

                continue



            for job in job_data[:max_jobs_per_role]:

                if jobs_saved >= max_jobs_per_role:

                    break

                try:

                    job_url = job["url"]

                    job_title = job["title"]



                    # Duplicate check

                    with get_db_connection() as conn:

                        cur = conn.cursor()

                        cur.execute("SELECT id FROM job_applications WHERE job_url = ?", (job_url,))

                        if cur.fetchone():

                            continue



                    if progress_callback:

                        progress_callback(f"Wellfound: Reading '{job_title}'...", 10)



                    # Open detail in new tab

                    detail_page = await context.new_page()

                    try:

                        await detail_page.goto(job_url, wait_until="domcontentloaded", timeout=20000)

                        await detail_page.wait_for_timeout(3000)



                        # Check for login wall on detail page

                        detail_text = await detail_page.locator("body").inner_text()

                        if "Sign up to apply" in detail_text or "Create an account" in detail_text:

                            await detail_page.close()

                            if progress_callback:

                                progress_callback(f"Wellfound: Login required for {job_title}. Skipping.", 10)

                            continue



                        # Extract company

                        company = ""

                        for sel in ["h2", "[class*='company']", "[class*='startup']", "a[href*='/company/']"]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                company = (await el.first.inner_text()).strip()

                                if company and len(company) < 100:

                                    break



                        # Extract description â€” Wellfound puts everything in the job description section

                        desc_text = ""

                        for sel in [

                            "[class*='description']",

                            "[class*='job-desc']",

                            "[class*='JobDescription']",

                            "div[data-testid='job-description']",

                            "main p",

                            "article"

                        ]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                text = (await el.first.inner_text()).strip()

                                if text and len(text) > 100:

                                    desc_text = text

                                    break



                        if not desc_text:

                            # Grab full page text as last resort

                            desc_text = detail_text[:4000]



                    finally:

                        await detail_page.close()



                    if not desc_text:

                        continue



                    # AI Scoring

                    prompt = f"""You are an expert ATS recruiter. Compare this candidate profile to the job description and output a match score.



Candidate Profile:

{profile_json}



Job Title: {job_title}

Company: {company}

Job Description:

{desc_text[:4000]}



Output ONLY valid JSON in this exact format (no markdown, no explanation):

{{"score": 85, "reason": "brief reason"}}"""



                    
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
                        if progress_callback:
                            progress_callback(f"❌ All brains failed for {job_title}. Skipping.", 10)
                        continue

                    if score >= match_threshold:

                        if progress_callback:

                            progress_callback(f"âœ… Wellfound MATCH: {job_title} ({score}%)", 10)

                        with get_db_connection() as conn:

                            cur = conn.cursor()

                            try:

                                cur.execute("""

                                    INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)

                                    VALUES (?, ?, ?, ?, ?, 'pending_approval', ?)

                                """, ("wellfound", str(hash(job_url)), job_title, company, job_url, score))

                                conn.commit()

                                jobs_saved += 1

                            except sqlite3.IntegrityError:

                                pass

                    else:

                        if progress_callback:

                            progress_callback(f"âŒ Wellfound skip: {job_title} ({score}%)", 10)



                except Exception as e:

                    if progress_callback:

                        progress_callback(f"Wellfound: Error on job: {e}", 10)

                    continue



        await browser.close()



    if progress_callback:

        progress_callback("âœ… Wellfound scraping complete!", 100)





if __name__ == "__main__":

    asyncio.run(scrape_wellfound_jobs(["Python Developer"], "India", max_jobs_per_role=5, match_threshold=50))


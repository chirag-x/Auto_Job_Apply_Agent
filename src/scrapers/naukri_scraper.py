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





async def scrape_naukri_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None, headless=True):

    """

    Scrapes Naukri.com for jobs matching the given roles and location.

    Scores each job with Groq and saves >= match_threshold% to the DB.

    """

    state_file = os.path.join(os.path.dirname(__file__), '..', '..', 'storageState_naukri.json')

    state_file = os.path.abspath(state_file)



    if not os.path.exists(state_file):

        if progress_callback:

            progress_callback("Error: Naukri session not found. Please login via Session Manager.", 0)

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

        progress_callback("Naukri: Launching headless browser...", 5)



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

            location_encoded = urllib.parse.quote(location if location != "Both" else "India")

            role_slug = role.lower().replace(" ", "-")



            # Naukri search URL â€” use keyword search which is most reliable

            search_url = f"https://www.naukri.com/{role_slug}-jobs?k={role_encoded}&l={location_encoded}&jobAge=7&start={start_offset}"



            if progress_callback:

                progress_callback(f"Naukri [{role_idx+1}/{len(roles)}]: Searching '{role}'...", 10)



            try:

                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)

                await page.wait_for_timeout(3000)

            except Exception as e:

                if progress_callback:

                    progress_callback(f"Naukri: Failed to load search page: {e}", 10)

                continue



            # Collect job links directly â€” most robust approach

            # Naukri job links contain /job-listings- in their href

            job_links = await page.locator('a[href*="naukri.com"]').all()

            # Filter to only actual job listing links

            job_data = []

            seen_urls = set()

            for link in job_links:

                try:

                    href = await link.get_attribute("href") or ""

                    text = (await link.inner_text()).strip()

                    if "job-listings" in href and href not in seen_urls and text:

                        job_data.append({"url": href, "title": text})

                        seen_urls.add(href)

                except:

                    continue



            if not job_data:

                # Fallback: try to get all article/div job cards and extract title + href

                try:

                    cards = await page.locator('article, .jobTuple, .srp-jobtuple-wrapper').all()

                    for card in cards:

                        try:

                            anchor = card.locator('a').first

                            href = await anchor.get_attribute("href") or ""

                            text = (await anchor.inner_text()).strip()

                            if href and text and href not in seen_urls:

                                full_url = href if href.startswith("http") else "https://www.naukri.com" + href

                                job_data.append({"url": full_url, "title": text})

                                seen_urls.add(full_url)

                        except:

                            continue

                except:

                    pass



            if not job_data:

                if progress_callback:

                    progress_callback(f"Naukri: No jobs found for '{role}'. Try different search terms.", 10)

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



                    # Navigate to job detail for description + company

                    if progress_callback:

                        progress_callback(f"Naukri: Reading '{job_title}'...", 10)



                    detail_page = await context.new_page()

                    try:

                        await detail_page.goto(job_url, wait_until="domcontentloaded", timeout=20000)

                        await detail_page.wait_for_timeout(2000)



                        # Extract company

                        company = ""

                        for sel in [".jd-header-comp-name a", "[class*='comp-name']", ".company-name", "a.comp-name"]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                company = (await el.first.inner_text()).strip()

                                if company:

                                    break



                        # Extract description

                        desc_text = ""

                        for sel in [".job-desc", ".jd-desc", "[class*='job-description']", ".dang-inner-html"]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                desc_text = (await el.first.inner_text()).strip()

                                if desc_text:

                                    break



                        if not desc_text:

                            # Last resort: get all text from main content

                            try:

                                desc_text = await detail_page.locator("main, #job-desc, article").first.inner_text()

                            except:

                                pass



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

                            progress_callback(f"âœ… Naukri MATCH: {job_title} ({score}%)", 10)

                        with get_db_connection() as conn:

                            cur = conn.cursor()

                            try:

                                cur.execute("""

                                    INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)

                                    VALUES (?, ?, ?, ?, ?, 'pending_approval', ?)

                                """, ("naukri", str(hash(job_url)), job_title, company, job_url, score))

                                conn.commit()

                                jobs_saved += 1

                            except sqlite3.IntegrityError:

                                pass

                    else:

                        if progress_callback:

                            progress_callback(f"âŒ Naukri skip: {job_title} ({score}%)", 10)



                except Exception as e:

                    if progress_callback:

                        progress_callback(f"Naukri: Error on job card: {e}", 10)

                    continue



        await browser.close()



    if progress_callback:

        progress_callback("âœ… Naukri scraping complete!", 100)





if __name__ == "__main__":

    asyncio.run(scrape_naukri_jobs(["Python Developer"], "India", max_jobs_per_role=5, match_threshold=50))


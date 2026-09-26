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





async def scrape_indeed_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None, headless=True):

    """

    Scrapes Indeed.com for jobs matching the given roles and location.

    Scores each job with Groq and saves >= match_threshold% to the DB.

    """

    state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'storageState_indeed.json'))



    if not os.path.exists(state_file):

        if progress_callback:

            progress_callback("Error: Indeed session not found. Please login via Session Manager.", 0)

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

        progress_callback("Indeed: Launching headless browser...", 5)



    async with async_playwright() as p:

        browser = await p.chromium.launch(headless=headless)

        context = await browser.new_context(

            storage_state=state_file,

            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

        )

        page = await context.new_page()
        # Add basic stealth to bypass simple Cloudflare checks
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")



        for role_idx, role in enumerate(roles):

            role = role.strip()

            if not role:

                continue



            jobs_saved = 0

            role_encoded = urllib.parse.quote(role)



            # Indeed location handling

            if location == "Remote":

                loc_param = "remote"

            elif location == "India":

                loc_param = "India"

            else:

                loc_param = "India"  # Both â€” India + remote jobs



            loc_encoded = urllib.parse.quote(loc_param)

            search_url = f"https://in.indeed.com/jobs?q={role_encoded}&l={loc_encoded}&start={start_offset}&fromage=7"



            if progress_callback:

                progress_callback(f"Indeed [{role_idx+1}/{len(roles)}]: Searching '{role}'...", 10)



            try:
                await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Cloudflare Detection Loop
                for _ in range(30):
                    title = await page.title()
                    page_text = await page.locator("body").inner_text()
                    if "Just a moment..." in title or "Additional Verification Required" in page_text or "cloudflare" in page_text.lower():
                        if progress_callback:
                            progress_callback(f"Indeed: Cloudflare detected! Please solve it in the visible browser...", 10)
                        await page.wait_for_timeout(5000)
                    else:
                        break
                
                # Sometimes Indeed fills the query parameters into the search bar but doesn't actually trigger the search!
                # We need to manually click the "Find jobs" or "Search" button if it's there.
                find_btn = page.locator("button.yosegi-InlineWhatWhere-primaryButton, button:has-text('Find jobs'), button:has-text('Search')").first
                if await find_btn.count() > 0 and await find_btn.is_visible():
                    if progress_callback:
                        progress_callback(f"Indeed: Clicking 'Find jobs' button to force search...", 10)
                    await find_btn.click()
                    await page.wait_for_timeout(3000)

            except Exception as e:

                if progress_callback:

                    progress_callback(f"Indeed: Failed to load search page: {e}", 10)

                continue



            # Indeed job links: /rc/clk or /pagead/clk or /viewjob or /company URLs

            # The most reliable: .jcs-JobTitle links which are the actual job title anchors

            all_job_links = await page.locator('a.jcs-JobTitle, a[data-jk], h2.jobTitle a').all()



            job_data = []

            seen_keys = set()

            for link in all_job_links:

                try:

                    href = await link.get_attribute("href") or ""

                    jk = await link.get_attribute("data-jk") or ""

                    title = (await link.inner_text()).strip()



                    # Build canonical Indeed job URL

                    if jk and jk not in seen_keys:

                        job_url = f"https://in.indeed.com/viewjob?jk={jk}"

                        seen_keys.add(jk)

                    elif "/viewjob" in href and href not in seen_keys:

                        job_url = "https://in.indeed.com" + href if not href.startswith("http") else href

                        seen_keys.add(href)

                    else:

                        continue



                    if title:

                        job_data.append({"url": job_url, "title": title})

                except:

                    continue



            if not job_data:

                # Fallback: grab all links containing /viewjob or /rc/clk

                fallback_links = await page.locator('a[href*="viewjob"], a[href*="/rc/clk"]').all()

                for link in fallback_links:

                    try:

                        href = await link.get_attribute("href") or ""

                        title = (await link.inner_text()).strip()

                        if href and title and href not in seen_keys:

                            full_url = "https://in.indeed.com" + href if not href.startswith("http") else href

                            job_data.append({"url": full_url, "title": title})

                            seen_keys.add(href)

                    except:

                        continue



            if not job_data:

                if progress_callback:

                    progress_callback(f"Indeed: No jobs found for '{role}'. Try a different search term.", 10)

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

                        progress_callback(f"Indeed: Reading '{job_title}'...", 10)



                    # Open job detail in new tab

                    detail_page = await context.new_page()

                    try:

                        await detail_page.goto(job_url, wait_until="domcontentloaded", timeout=20000)
                        await detail_page.wait_for_timeout(2000)
                        
                        # Cloudflare Detection Loop
                        for _ in range(30):
                            d_title = await detail_page.title()
                            d_text = await detail_page.locator("body").inner_text()
                            if "Just a moment..." in d_title or "Additional Verification Required" in d_text or "cloudflare" in d_text.lower():
                                if progress_callback:
                                    progress_callback(f"Indeed: Cloudflare detected on job page! Please solve it...", 10)
                                await detail_page.wait_for_timeout(5000)
                            else:
                                break
                        



                        # Extract company

                        company = ""

                        for sel in [

                            "[data-testid='inlineHeader-companyName']",

                            ".icl-u-lg-mr--sm.icl-u-xs-mr--xs",

                            "[class*='companyName']",

                            "span.companyName"

                        ]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                company = (await el.first.inner_text()).strip()

                                if company:

                                    break



                        # Extract job description

                        desc_text = ""

                        for sel in [

                            "#jobDescriptionText",

                            "[class*='jobsearch-JobComponent-description']",

                            ".jobsearch-jobDescriptionText",

                            "[data-testid='jobsearch-JobComponent-description']"

                        ]:

                            el = detail_page.locator(sel)

                            if await el.count() > 0:

                                desc_text = (await el.first.inner_text()).strip()

                                if desc_text:

                                    break



                        if not desc_text:

                            # Last resort

                            try:

                                desc_text = await detail_page.locator("body").inner_text()

                                desc_text = desc_text[:4000]

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

                            progress_callback(f"âœ… Indeed MATCH: {job_title} ({score}%)", 10)

                        with get_db_connection() as conn:

                            cur = conn.cursor()

                            try:

                                cur.execute("""

                                    INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)

                                    VALUES (?, ?, ?, ?, ?, 'pending_approval', ?)

                                """, ("indeed", str(hash(job_url)), job_title, company, job_url, score))

                                conn.commit()

                                jobs_saved += 1

                            except sqlite3.IntegrityError:

                                pass

                    else:

                        if progress_callback:

                            progress_callback(f"âŒ Indeed skip: {job_title} ({score}%)", 10)



                except Exception as e:

                    if progress_callback:

                        progress_callback(f"Indeed: Error on job: {e}", 10)

                    continue



        await browser.close()



    if progress_callback:

        progress_callback("âœ… Indeed scraping complete!", 100)





if __name__ == "__main__":

    asyncio.run(scrape_indeed_jobs(["Python Developer"], "India", max_jobs_per_role=5, match_threshold=50))


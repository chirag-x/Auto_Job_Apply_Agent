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

async def scrape_internshala_jobs(roles, location, start_offset=0, max_jobs_per_role=50, match_threshold=80, progress_callback=None, headless=True):
    profile = get_user_profile()
    if not profile:
        if progress_callback:
            progress_callback("Error: User profile not found.", 0)
        return

    configs = get_all_llm_configs()
    active_configs = [c for c in configs if c.get('is_active')]
    if not active_configs:
        if progress_callback:
            progress_callback("Error: No active LLM config found.", 0)
        return

    profile_json = json.dumps(profile)
    state_file = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'storageState_internshala.json'))

    if not os.path.exists(state_file):
        if progress_callback:
            progress_callback("Error: Please login via Session Manager first.", 0)
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless)
        context = await browser.new_context(storage_state=state_file)
        page = await context.new_page()

        for role_idx, role in enumerate(roles):
            role = role.strip()
            if not role: continue

            jobs_saved = 0
            role_hyphenated = role.lower().replace(' ', '-')
            
            base_urls = [
                f"https://internshala.com/internships/keywords-{role_hyphenated}",
                f"https://internshala.com/jobs/keywords-{role_hyphenated}"
            ]
            
            for base_url in base_urls:
                if jobs_saved >= max_jobs_per_role:
                    break
                    
                if progress_callback:
                    progress_callback(f"Internshala [{role_idx+1}/{len(roles)}]: Loading '{base_url}'...", 10)
                    
                try:
                    await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_timeout(3000)
                    
                    # Check for login wall
                    if "login" in page.url:
                        if progress_callback:
                            progress_callback("Error: Login required. Update session.", 0)
                        await browser.close()
                        return

                    # Scroll down to reveal the keyword search sidebar
                    await page.evaluate("window.scrollBy(0, 800)")
                    await page.wait_for_timeout(1500)
                    
                    # Instead of typing, the URL already pre-filled the keyword box! 
                    # We just need to click the search button to trigger the AJAX job load.
                    search_btn = page.locator("button#keyword_search_button, i.ic-search, .search_btn").first
                    if await search_btn.count() > 0:
                        await search_btn.click(force=True)
                        await page.wait_for_timeout(4000)
                    else:
                        if progress_callback:
                            progress_callback("Internshala: Could not find search button to trigger refresh.", 10)

                except Exception as e:
                    if progress_callback:
                        progress_callback(f"Internshala: Failed to load page: {e}", 10)
                    continue

                                # Find all job/internship detail links directly
                all_links = await page.locator('a[href*="/job/detail/"], a[href*="/internship/detail/"], .view_detail_button').all()
                if not all_links:
                    all_links = await page.locator('.individual_internship .heading_4_5 a, .internship_meta .profile a').all()
                
                seen_urls = set()
                
                for link in all_links:
                    if jobs_saved >= max_jobs_per_role:
                        break

                    try:
                        raw_title = (await link.inner_text()).strip()
                        if not raw_title:
                            continue
                            
                        # Split by newline and take the first line to prevent the giant card string bug
                        job_title = raw_title.split('\n')[0].strip()
                        
                        if len(job_title) < 3:
                            continue
                            
                        company = "Unknown"  # We'll extract this from the detail page
                        
                        job_path = await link.get_attribute("href")
                        if not job_path:
                            # Try looking for a nested link or parent link if this is a button
                            nested = link.locator("a").first
                            if await nested.count() > 0:
                                job_path = await nested.get_attribute("href")
                            else:
                                parent = link.locator("..").locator("a").first
                                if await parent.count() > 0:
                                    job_path = await parent.get_attribute("href")
                                    
                        if not job_path:
                            continue
                            
                        job_url = "https://internshala.com" + job_path if job_path.startswith("/") else job_path
                        
                        # Prevent duplicate rate-limiting crash
                        if job_url in seen_urls:
                            continue
                        seen_urls.add(job_url)

                        # Check DB
                        with get_db_connection() as conn:
                            cur = conn.cursor()
                            cur.execute("SELECT id FROM job_applications WHERE job_url = ?", (job_url,))
                            if cur.fetchone():
                                continue

                        if progress_callback:
                            progress_callback(f"Internshala: Reading '{job_title} - {company}'...", 10)

                        detail_page = await context.new_page()
                        try:
                            await detail_page.goto(job_url, timeout=15000)
                            await detail_page.wait_for_timeout(2000)
                            
                            # Extract company if we didn't get it
                            comp_loc = detail_page.locator(".company-name, .company_name, .profile_on_detail_page").first
                            if await comp_loc.count() > 0:
                                company = (await comp_loc.inner_text()).strip()
                                
                            desc_loc = detail_page.locator(".internship_details, .about-heading + div, .requirements, .text-container, .job_description, .detail-view, .detail_container")
                            if await desc_loc.count() > 0:
                                # Playwright strict mode: if multiple elements match, we must use all_inner_texts()
                                texts = await desc_loc.all_inner_texts()
                                desc_text = " ".join(texts)
                            else:
                                desc_text = ""
                                
                            if not desc_text:
                                desc_text = await detail_page.locator("body").inner_text()
                        except Exception as e:
                            desc_text = ""
                            if progress_callback:
                                progress_callback(f"Internshala: Error loading job details - {e}", 10)
                        finally:
                            await detail_page.close()

                        if not desc_text:
                            if progress_callback:
                                progress_callback(f"Internshala: Skip - Could not extract description for {job_title}", 10)
                            continue

                        prompt = f"""You are an expert ATS recruiter. Compare this candidate profile to the internship/job description and output a match score.

Candidate Profile:
{profile_json}

Job Title: {job_title}
Company: {company}
Description:
{desc_text[:4000]}

Output ONLY valid JSON in this exact format (no markdown, no explanation):
{{"score": 85, "reason": "brief reason"}}"""

                        score = None
                        for best in sorted(active_configs, key=lambda x: x.get('priority', 99)):
                            try:
                                llm = build_llm(best, temperature=0.0)
                                llm_resp = await asyncio.to_thread(llm.invoke, prompt)
                                raw = llm_resp.content.strip().strip("```json").strip("```").strip()
                                data = json.loads(raw)
                                score = data.get("score")
                                break
                            except Exception as e:
                                if progress_callback:
                                    progress_callback(f"⚠️ Brain '{best['model_name']}' failed ({type(e).__name__}: {e}). Trying next...", 10)
                                continue

                        if score is None:
                            if progress_callback:
                                progress_callback(f"❌ All brains failed for {job_title}. Skipping.", 10)
                            continue

                        if score >= match_threshold:
                            if progress_callback:
                                progress_callback(f"✅ Internshala MATCH: {job_title} ({score}%)", 10)
                            with get_db_connection() as conn:
                                cur = conn.cursor()
                                try:
                                    cur.execute('''
                                        INSERT INTO job_applications (platform, job_id, job_title, company, job_url, status, match_score)
                                        VALUES (?, ?, ?, ?, ?, 'pending_approval', ?)
                                    ''', ("internshala", str(hash(job_url)), job_title, company, job_url, score))
                                    conn.commit()
                                    jobs_saved += 1
                                except sqlite3.IntegrityError:
                                    pass
                        else:
                            if progress_callback:
                                progress_callback(f"❌ Internshala skip: {job_title} ({score}%)", 10)

                    except Exception as e:
                        if progress_callback:
                            progress_callback(f"Internshala: Error on listing: {e}", 10)

        await browser.close()
    if progress_callback:
            progress_callback("✅ Internshala scraping complete!", 100)

if __name__ == "__main__":
    asyncio.run(scrape_internshala_jobs(["Python"], "India", max_jobs_per_role=2))

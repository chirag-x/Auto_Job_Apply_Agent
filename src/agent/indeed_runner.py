import argparse
import asyncio
import os
import sys

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from playwright.async_api import async_playwright
from src.agent.langchain_llm import build_llm
from src.core.crud import get_all_llm_configs, get_user_profile

PLATFORM = "Indeed"
SESSION_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')), "storageState_indeed.json")

def get_active_configs():
    pass

async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Indeed Job URL")
    parser.add_argument("--headless", action="store_true", help="Run in headless mode")
    args = parser.parse_args()
    url = args.url
    headless = args.headless

    if not os.path.exists(SESSION_FILE):
        print(f"[{PLATFORM}] ERROR: Session file not found at {SESSION_FILE}. Please log in first.")
        sys.exit(1)

    try:
        llm = build_llm()
        profile = get_user_profile() or {}

        print(f"\\n[{PLATFORM}] Initializing Playwright (Headless: {headless})...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=headless)
            
            context = await browser.new_context(
                storage_state=SESSION_FILE,
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            print(f"[{PLATFORM}] Loaded existing Indeed session.")

            page = await context.new_page()
            # Basic bypass for webdriver detection
            await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

            print(f"[{PLATFORM}] Navigating to: {url}")
            await page.goto(url)
            await page.wait_for_timeout(3000)

            # Check if we already applied (Aggressive check for the exact word 'Applied' on a visible button/span)
            found_applied = False
            # Find elements that contain exactly the word "Applied" (or similar button-like structures)
            applied_locs = await page.locator("button, a, div[role='button'], span").all()
            for el in applied_locs:
                try:
                    if await el.is_visible(timeout=100):
                        inner = (await el.inner_text()).strip().lower()
                        # If the element exclusively says "applied" (or very close to it), it's the button
                        if inner == "applied" or inner == "applied\\n":
                            found_applied = True
                            break
                except Exception:
                    continue
                    
            if found_applied:
                print(f"[{PLATFORM}] Job already applied! Marking as success.")
                print(f"[{PLATFORM}] Application submitted successfully!")
                await page.wait_for_timeout(2000)
                await browser.close()
                return

            # --- Find and click Apply button ---
            apply_clicked = False
            apply_selectors = [
                "button#applyButtonLinkContainer",
                "button:has-text('Apply now')",
                "a:has-text('Apply now')",
                "#indeedApplyButton",
                ".jobsearch-IndeedApplyButton-button"
            ]
            
            for attempt in range(3):
                for sel in apply_selectors:
                    try:
                        btn = page.locator(sel).first
                        if await btn.is_visible(timeout=3000):
                            print(f"[{PLATFORM}] Found Apply button: '{sel}'. Clicking...")
                            await btn.click(force=True)
                            await page.wait_for_timeout(5000)
                            apply_clicked = True
                            break
                    except Exception:
                        continue
                
                if apply_clicked: break
                
                print(f"[{PLATFORM}] Manual intervention required - could not find Apply button")
                print(f"[{PLATFORM}] Waiting 60 seconds (attempt {attempt+1}/3)...")
                await page.wait_for_timeout(60000)

            if not apply_clicked:
                print(f"[{PLATFORM}] Manual intervention required - could not find Apply button after all attempts.")
                await browser.close()
                return

            print(f"[{PLATFORM}] Indeed uses a highly dynamic multi-page iframe application flow.")
            print(f"[{PLATFORM}] Starting Smart iFrame Engine...")
            
            success = False
            # We will loop to traverse the multi-page iframe
            # Wait up to 600 seconds total
            for _ in range(120): # 120 * 5s = 600s
                try:
                    # 1. Check for success text on main page or iframe
                    success_text = page.locator("text='Your application has been submitted', text='Application submitted', text='applied', h1:has-text('submitted')")
                    if await success_text.count() > 0 and await success_text.first.is_visible(timeout=1000):
                        success = True
                        break
                        
                    iframe = page.frame_locator("iframe[title*='Apply'], iframe[src*='indeedapply']")
                    
                    if await iframe.locator("text='Your application has been submitted'").count() > 0:
                        success = True
                        break
                        
                    # 2. Check if we are stuck on a CAPTCHA
                    if await iframe.locator("iframe[title*='recaptcha'], iframe[title*='hCaptcha']").count() > 0:
                        print(f"[{PLATFORM}] CAPTCHA detected. Waiting for user to solve it manually...")
                        await page.wait_for_timeout(5000)
                        continue

                    # 3. Look for standard Indeed buttons (Continue, Next, Submit, Return to Job Search)
                    btn_selectors = [
                        "button:has-text('Continue')",
                        "button:has-text('Next')",
                        "button:has-text('Review your application')",
                        "button:has-text('Submit your application')",
                        "button:has-text('Apply')",
                        ".ia-continueButton"
                    ]
                    
                    clicked_something = False
                    for b_sel in btn_selectors:
                        btn = iframe.locator(b_sel).first
                        if await btn.count() > 0 and await btn.is_visible():
                            # Before clicking Continue, check if there's any unfilled inputs
                            inputs = await iframe.locator("input:not([type='hidden']):not([type='submit']), textarea, select").all()
                            
                            for field in inputs:
                                try:
                                    tag = await field.evaluate("el => el.tagName.toLowerCase()")
                                    field_type = await field.get_attribute("type") or ""
                                    name_attr = await field.get_attribute("name") or ""
                                    placeholder = await field.get_attribute("placeholder") or ""
                                    aria_label = await field.get_attribute("aria-label") or ""
                                    
                                    if field_type in ("hidden", "submit", "button", "reset", "file", "checkbox", "radio"):
                                        continue
                                    
                                    val = await field.input_value()
                                    if val and val.strip():
                                        continue

                                    question = aria_label or placeholder or name_attr or f"{tag} field"
                                    if not question.strip():
                                        continue

                                    print(f"[{PLATFORM}] Asking Groq for iframe field: '{question}'")
                                    prompt = f"User Profile: {profile}\\nQuestion: {question}\\nAnswer concisely based on the profile. Raw text only."
                                    response = await asyncio.to_thread(llm.invoke, prompt)
                                    answer = response.content.strip()
                                    if tag == "select":
                                        try:
                                            await field.select_option(label=answer, timeout=2000)
                                        except Exception:
                                            try:
                                                await field.select_option(index=1, timeout=2000)
                                            except Exception:
                                                pass
                                    else:
                                        await field.fill(answer)
                                        await page.wait_for_timeout(500)
                                except Exception as e:
                                    print(f"[{PLATFORM}] Could not fill iframe field: {e}")
                            
                            print(f"[{PLATFORM}] Found '{b_sel}' button. Clicking...")
                            await btn.scroll_into_view_if_needed()
                            await btn.click(force=True)
                            await page.wait_for_timeout(3000)
                            clicked_something = True
                            break
                            
                    if clicked_something:
                        continue
                        
                except Exception as e:
                    pass
                    
                await page.wait_for_timeout(5000)
                
            if success:
                print(f"[{PLATFORM}] Application submitted successfully!")
            else:
                print(f"[{PLATFORM}] Timeout reached or submission could not be verified automatically.")
            
            print(f"[{PLATFORM}] Automation complete. Keeping browser open for 5 seconds for review...")
            await page.wait_for_timeout(5000)
            await browser.close()

    except Exception as e:
        print(f"[{PLATFORM}] Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import os
import sys
import argparse
import json

# Add project root to Python path (3 levels up from src/agent/)
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from playwright.async_api import async_playwright
from src.agent.langchain_llm import build_llm
from src.core.crud import get_all_llm_configs, get_user_profile

PLATFORM = "Internshala"
SESSION_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')), "storageState_internshala.json")

APPLY_SELECTORS = [
    "button.apply_now_btn",
    "a.apply-btn",
    "button:has-text('Apply Now')",
    "a:has-text('Apply Now')",
]


def get_active_configs():
    configs = get_all_llm_configs()
    active = [c for c in configs if c.get('is_active')]
    active.sort(key=lambda x: x.get('priority', 99))
    if not active:
        raise ValueError("No active LLM found in database.")
    return active

async def invoke_with_fallback(configs, prompt, temperature=0.2, max_tokens=500):
    import asyncio
    for best in configs:
        try:
            llm = build_llm(best, temperature=temperature, max_tokens=max_tokens)
            return await asyncio.to_thread(llm.invoke, prompt)
        except Exception as e:
            print(f"⚠️ Brain '{best['model_name']}' failed ({e}). Trying next...")
            continue
    raise Exception("All active brains failed.")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="Internshala Internship/Job URL")
    args = parser.parse_args()
    url = args.url

    # Validate session file exists
    if not os.path.exists(SESSION_FILE):
        print(f"[{PLATFORM}] ERROR: Session file not found at {SESSION_FILE}. Please log in first.")
        sys.exit(1)

    try:
        configs = get_active_configs()
        profile = get_user_profile() or {}

        print(f"\n[{PLATFORM}] Initializing Playwright...")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=False)  # Keep visible for user to see and intervene

            context = await browser.new_context(storage_state=SESSION_FILE)
            print(f"[{PLATFORM}] Loaded existing Internshala session.")

            page = await context.new_page()

            print(f"[{PLATFORM}] Navigating to: {url}")
            await page.goto(url)
            await page.wait_for_timeout(3000)

            # --- Find and click Apply button ---
            apply_clicked = False
            for attempt_cycle in range(3):
                for selector in APPLY_SELECTORS:
                    try:
                        locator = page.locator(selector).first
                        if await locator.is_visible(timeout=3000):
                            print(f"[{PLATFORM}] Found Apply button with selector: '{selector}'. Clicking...")
                            await locator.click(force=True)
                            await page.wait_for_timeout(3000)
                            apply_clicked = True
                            break
                    except Exception:
                        continue

                if apply_clicked:
                    break

                print(f"[{PLATFORM}] Manual intervention required - could not find Apply button")
                print(f"[{PLATFORM}] Waiting 60 seconds for manual intervention (attempt {attempt_cycle + 1}/3)...")
                await page.wait_for_timeout(60000)

            if not apply_clicked:
                print(f"[{PLATFORM}] Manual intervention required - could not find Apply button after all attempts.")
                await browser.close()
                return

            await page.wait_for_timeout(2000)

            # --- Handle Intermediate Resume Page ---
            try:
                proceed_btn = page.locator("button:has-text('Proceed to application'), a:has-text('Proceed to application'), #proceed").first
                if await proceed_btn.is_visible(timeout=5000):
                    print(f"[{PLATFORM}] Detected Internshala Intermediate Resume page.")
                    print(f"[{PLATFORM}] Resume is already complete. Clicking 'Proceed to application' to bypass...")
                    await proceed_btn.click(force=True)
                    await page.wait_for_timeout(3000)
            except Exception as e:
                pass

            # ----------------------------------------------------------------
            # a. Cover Letter textarea
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Looking for Cover Letter / Personal Statement textarea...")
            cover_letter_selectors = [
                "textarea[name*='cover']",
                "textarea[placeholder*='cover']",
                "textarea[placeholder*='letter']",
                "textarea[id*='cover']",
                "textarea",
            ]

            personal_statement = profile.get('personal_statement', '') or profile.get('cover_letter', '') or ""

            for sel in cover_letter_selectors:
                try:
                    cover_el = page.locator(sel).first
                    if await cover_el.is_visible(timeout=3000):
                        print(f"[{PLATFORM}] Found cover letter textarea with '{sel}'. Generating customized cover letter...")

                        # Extract internship/job title from page title for customization
                        page_title = await page.title()

                        prompt = f"""
You are an AI job assistant writing a cover letter for an Internshala application.

User Profile:
{profile}

Target Role/Page: {page_title}

User's Personal Statement (base):
{personal_statement}

Write a concise, professional cover letter (3-4 sentences) customized for this role.
Use the personal statement as a base but tailor it to the role.
Respond with ONLY the cover letter text — no preamble, no JSON, no markdown.
"""
                        response = await invoke_with_fallback(configs, prompt)
                        cover_letter_text = response.content.strip()
                        print(f"[{PLATFORM}] Generated cover letter ({len(cover_letter_text)} chars).")
                        await cover_el.fill(cover_letter_text)
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # ----------------------------------------------------------------
            # b. Availability / Start Date
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Looking for availability / start date field...")
            availability = (
                profile.get('available_start_date', '')
                or profile.get('availability', '')
                or profile.get('notice_period', '')
                or "Immediately"
            )

            avail_selectors = [
                "input[name*='availability']",
                "input[placeholder*='availability']",
                "input[placeholder*='start']",
                "input[name*='start_date']",
                "input[id*='availability']",
            ]

            for sel in avail_selectors:
                try:
                    avail_el = page.locator(sel).first
                    if await avail_el.is_visible(timeout=2000):
                        print(f"[{PLATFORM}] Filling availability field with: '{availability}'")
                        await avail_el.fill(str(availability))
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # ----------------------------------------------------------------
                                    # c. Custom questions — use Groq (Sniper AI pattern)
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Scanning for custom questions...")
            try:
                groups = await page.locator('.form-group').all()
                for group in groups:
                    if not await group.is_visible():
                        continue
                        
                    question_text = await group.evaluate("""el => {
                        const label = el.querySelector('label.control-label, label.question');
                        if (label) return label.innerText.trim();
                        
                        // Internshala specific fallback: text just before the input or the whole div text
                        if(el.innerText) return el.innerText.trim().split('\\n')[0];
                        return '';
                    }""")
                    
                    # Textarea / Text Inputs
                    text_input = group.locator('textarea, input[type="text"]').first
                    if await text_input.count() > 0 and await text_input.is_visible():
                        if (await text_input.input_value()).strip(): continue
                        # The question might be the placeholder if innerText failed
                        placeholder = await text_input.get_attribute("placeholder") or ""
                        q = question_text if question_text else placeholder
                        print(f"[{PLATFORM}] Asking Groq for custom question: '{q}'")
                        prompt = f"User Profile: {profile}\nQuestion: {q}\nAnswer honestly based on the profile in 1-2 sentences. Do not use generic placeholders. Raw text only."
                        response = await invoke_with_fallback(configs, prompt)
                        await text_input.fill(response.content.strip())
                        await page.wait_for_timeout(500)
                        continue
                        
                    # Radio Buttons
                    radios = group.locator('input[type="radio"]')
                    if await radios.count() > 0:
                        # Check if any is checked
                        is_checked = await group.evaluate("""el => { return el.querySelector('input[type="radio"]:checked') !== null; }""")
                        if is_checked: continue
                        
                        options = await group.evaluate("""el => { 
                            return Array.from(el.querySelectorAll('label, .radio')).map(l => l.innerText.trim()).filter(t => t.length > 0).join(' | '); 
                        }""")
                        print(f"[{PLATFORM}] Asking Groq for radio question: '{question_text}' (Options: {options})")
                        prompt = f"User Profile: {profile}\nQuestion: {question_text}\nOptions: {options}\nChoose the best option. Reply with ONLY the exact option text, nothing else."
                        response = await invoke_with_fallback(configs, prompt)
                        answer = response.content.strip().lower()
                        # Click the matching radio label
                        for i in range(await radios.count()):
                            radio = radios.nth(i)
                            r_label = await radio.evaluate("""r => { 
                                const id = r.id; 
                                const lbl = document.querySelector('label[for="'+id+'"]'); 
                                if (lbl) return lbl.innerText.trim();
                                const parent = r.closest('label');
                                if (parent) return parent.innerText.trim();
                                return r.value;
                            }""")
                            if r_label and (answer in r_label.lower() or r_label.lower() in answer):
                                await radio.click(force=True)
                                await page.wait_for_timeout(500)
                                break
                        continue
                        
            except Exception as e:
                print(f"[{PLATFORM}] Error scanning custom questions: {e}")

            # --- Submit ---
            print(f"[{PLATFORM}] Starting Smart Loop for Submission...")
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "button:has-text('Submit')",
            ]

            success = False
            # Loop for up to 10 minutes (120 * 5s) waiting for user to clear popups or complete manual intervention
            for attempt in range(120):
                # Check if we naturally landed on a success state by manual submission
                if "dashboard" in page.url.lower() or await page.locator("text='successfully', text='applied successfully'").count() > 0:
                    success = True
                    break

                submitted = False
                for sel in submit_selectors:
                    try:
                        submit_btn = page.locator(sel).first
                        if await submit_btn.is_visible(timeout=1000):
                            print(f"[{PLATFORM}] Clicking submit button: '{sel}'")
                            await submit_btn.click(force=True)
                            await page.wait_for_timeout(3000)
                            submitted = True
                            break
                    except Exception:
                        continue

                if submitted:
                    has_error = False
                    try:
                        error_loc = page.locator(".has-error, .field-error, .error, .help-block, text=This field is required").first
                        if await error_loc.is_visible(timeout=2000):
                            has_error = True
                    except Exception:
                        pass
                    
                    if has_error:
                        if attempt % 6 == 0:  # Print every 30s
                            print(f"[{PLATFORM}] Validation error or CAPTCHA detected. Please fix manually. Retrying...")
                    else:
                        success = True
                        break
                else:
                    if attempt % 6 == 0:  # Print every 30s
                        print(f"[{PLATFORM}] Submit button hidden (Popup?). Waiting for manual intervention...")
                        
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

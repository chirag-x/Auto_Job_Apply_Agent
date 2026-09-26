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

PLATFORM = "Naukri"
SESSION_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')), "storageState_naukri.json")

APPLY_SELECTORS = [
    "a.apply-button",
    "button[class*='apply']",
    "a[class*='apply']",
    "button:has-text('Apply')",
    "a:has-text('Apply')",
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
    parser.add_argument("--url", required=True, help="Naukri Job URL")
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
            print(f"[{PLATFORM}] Loaded existing Naukri session.")

            page = await context.new_page()

            print(f"[{PLATFORM}] Navigating to: {url}")
            await page.goto(url)
            await page.wait_for_timeout(3000)

            # Check for external redirect or closed jobs
            current_url = page.url
            if "naukri.com" not in current_url:
                print(f"[{PLATFORM}] WARNING: Job redirected to external site ({current_url}). Exiting gracefully.")
                await browser.close()
                return

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

            # --- Detect if a modal/new page appeared ---
            await page.wait_for_timeout(3000)
            
            # Naukri often opens the application in a NEW tab. Switch to it if it exists.
            if len(context.pages) > 1:
                print(f"[{PLATFORM}] Detected new tab opened. Switching to new tab...")
                page = context.pages[-1]
                await page.bring_to_front()
                await page.wait_for_timeout(2000)

            # Check for external site redirect after clicking apply
            current_url = page.url
            if "naukri.com" not in current_url:
                print(f"[{PLATFORM}] Apply redirected to external site ({current_url}).")
                print(f"[{PLATFORM}] Naukri jobs hosted on external sites require custom flows. Closing gracefully.")
                await browser.close()
                return

            # --- Fill application form fields using Groq ---
            print(f"[{PLATFORM}] Scanning form fields...")
            try:
                fields = await page.locator('input, textarea, select').all()
                print(f"[{PLATFORM}] Found {len(fields)} form field(s).")

                for field in fields:
                    try:
                        tag = await field.evaluate("el => el.tagName.toLowerCase()")
                        field_type = await field.get_attribute("type") or ""
                        name_attr = await field.get_attribute("name") or ""
                        placeholder = await field.get_attribute("placeholder") or ""
                        aria_label = await field.get_attribute("aria-label") or ""

                        # Determine label from nearby label element
                        label_text = await field.evaluate("""el => {
                            const id = el.id;
                            if (id) {
                                const label = document.querySelector('label[for="' + id + '"]');
                                if (label) return label.innerText.trim();
                            }
                            const parent = el.closest('.form-group, .field-wrapper, .input-wrapper, li, div');
                            if (parent) {
                                const label = parent.querySelector('label');
                                if (label) return label.innerText.trim();
                            }
                            return '';
                        }""")

                        question = label_text or aria_label or placeholder or name_attr or f"{tag} field"

                        if field_type in ("hidden", "submit", "button", "reset", "file", "checkbox", "radio"):
                            continue
                        if not question.strip():
                            continue

                        print(f"[{PLATFORM}] Asking Groq to answer field: '{question}'")

                        prompt = f"""
You are an AI job assistant filling out an application form on Naukri.

User Profile Details:
{profile}

Form field question/label: "{question}"
Field type: {tag} ({field_type if field_type else 'text'})

Respond with ONLY the raw answer text (no JSON, no explanation, no markdown).
Guidelines:
- For name fields: use the applicant's full name from profile.
- For email fields: use the applicant's email.
- For phone fields: use the applicant's phone number.
- For experience fields: use years of experience from profile (or "0" if unknown).
- For salary/CTC fields: use expected salary from profile (or "0" if unknown).
- For location fields: use city from profile (or "New Delhi" if unknown).
- For notice period: use notice period from profile (or "0" if unknown).
- Keep answers concise and professional.
"""
                        response = await invoke_with_fallback(configs, prompt)
                        answer = response.content.strip()
                        print(f"[{PLATFORM}] Groq answer for '{question}': '{answer[:80]}'")

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

                    except Exception as fe:
                        print(f"[{PLATFORM}] Could not fill field: {fe}")
                        continue

            except Exception as e:
                print(f"[{PLATFORM}] Error scanning form fields: {e}")

            # --- Look for Submit / Apply button ---
            print(f"[{PLATFORM}] Looking for Submit/Apply button...")
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "a:has-text('Submit')",
            ]

            submitted = False
            for sel in submit_selectors:
                try:
                    submit_btn = page.locator(sel).first
                    if await submit_btn.is_visible(timeout=3000):
                        print(f"[{PLATFORM}] Clicking submit button: '{sel}'")
                        await submit_btn.click(force=True)
                        await page.wait_for_timeout(5000)  # Wait 5 seconds after submit
                        submitted = True
                        break
                except Exception:
                    continue

            if submitted:
                print(f"[{PLATFORM}] Application submitted successfully!")
            else:
                print(f"[{PLATFORM}] Manual intervention required - could not find Submit button.")
                print(f"[{PLATFORM}] Waiting up to 600 seconds for manual submission...")
                await page.wait_for_timeout(600000)
                print(f"[{PLATFORM}] Continuing after manual intervention timeout.")

            print(f"[{PLATFORM}] Automation complete. Keeping browser open for 5 seconds for review...")
            await page.wait_for_timeout(5000)
            await browser.close()

    except Exception as e:
        print(f"[{PLATFORM}] Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

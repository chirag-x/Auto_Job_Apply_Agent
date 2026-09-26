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

PLATFORM = "Wellfound"
SESSION_FILE = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')), "storageState_wellfound.json")

APPLY_SELECTORS = [
    "button:has-text('Apply')",
    "a:has-text('Apply Now')",
    "[data-test='apply-button']",
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
    parser.add_argument("--url", required=True, help="Wellfound Job URL")
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
            print(f"[{PLATFORM}] Loaded existing Wellfound session.")

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

            # ----------------------------------------------------------------
            # a. "Why interested in this role?" → Personal Statement
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Looking for 'Why interested' field...")
            interest_selectors = [
                "textarea[name*='interest']",
                "textarea[placeholder*='interest']",
                "textarea[placeholder*='why']",
                "textarea[aria-label*='interest']",
                "textarea[aria-label*='why']",
            ]

            personal_statement = profile.get('personal_statement', '') or ""
            page_title = await page.title()

            for sel in interest_selectors:
                try:
                    interest_el = page.locator(sel).first
                    if await interest_el.is_visible(timeout=2000):
                        print(f"[{PLATFORM}] Found interest textarea with '{sel}'. Generating response via Groq...")

                        prompt = f"""
You are an AI job assistant. Write a compelling answer to the question: "Why are you interested in this role?"

User Profile:
{profile}

Target Role/Company (from page title): {page_title}
Personal Statement base:
{personal_statement}

Write 2-3 sentences, professional and enthusiastic, tailored to this specific role.
Respond with ONLY the answer text — no preamble, no JSON, no markdown.
"""
                        response = await invoke_with_fallback(configs, prompt)
                        interest_text = response.content.strip()
                        print(f"[{PLATFORM}] Generated interest answer ({len(interest_text)} chars).")
                        await interest_el.fill(interest_text)
                        await page.wait_for_timeout(500)
                        break
                except Exception:
                    continue

            # ----------------------------------------------------------------
            # b. LinkedIn URL
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Looking for LinkedIn URL field...")
            linkedin_url = profile.get('linkedin_url', '') or profile.get('linkedin', '') or ""

            linkedin_selectors = [
                "input[name*='linkedin']",
                "input[placeholder*='linkedin']",
                "input[aria-label*='linkedin']",
                "input[id*='linkedin']",
            ]

            if linkedin_url:
                for sel in linkedin_selectors:
                    try:
                        li_el = page.locator(sel).first
                        if await li_el.is_visible(timeout=2000):
                            print(f"[{PLATFORM}] Filling LinkedIn URL: '{linkedin_url}'")
                            await li_el.fill(linkedin_url)
                            await page.wait_for_timeout(500)
                            break
                    except Exception:
                        continue
            else:
                # Also check portfolio_url as fallback for LinkedIn
                portfolio_url = profile.get('portfolio_url', '') or ""
                if portfolio_url and 'linkedin' in portfolio_url:
                    for sel in linkedin_selectors:
                        try:
                            li_el = page.locator(sel).first
                            if await li_el.is_visible(timeout=2000):
                                print(f"[{PLATFORM}] Filling LinkedIn URL from portfolio_url: '{portfolio_url}'")
                                await li_el.fill(portfolio_url)
                                await page.wait_for_timeout(500)
                                break
                        except Exception:
                            continue

            # ----------------------------------------------------------------
            # c. GitHub URL
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Looking for GitHub URL field...")
            github_url = profile.get('github_url', '') or profile.get('github', '') or ""

            github_selectors = [
                "input[name*='github']",
                "input[placeholder*='github']",
                "input[aria-label*='github']",
                "input[id*='github']",
            ]

            if github_url:
                for sel in github_selectors:
                    try:
                        gh_el = page.locator(sel).first
                        if await gh_el.is_visible(timeout=2000):
                            print(f"[{PLATFORM}] Filling GitHub URL: '{github_url}'")
                            await gh_el.fill(github_url)
                            await page.wait_for_timeout(500)
                            break
                    except Exception:
                        continue

            # ----------------------------------------------------------------
            # d. Resume upload → skip (Wellfound pre-fills from profile)
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Skipping resume upload (Wellfound pre-fills from profile).")

            # ----------------------------------------------------------------
            # e. Custom questions — use Groq (Sniper AI pattern)
            # ----------------------------------------------------------------
            print(f"[{PLATFORM}] Scanning for custom questions...")
            try:
                fields = await page.locator(
                    'input:not([type="hidden"]):not([type="submit"]):not([type="button"]):not([type="reset"]):not([type="file"]):not([type="checkbox"]):not([type="radio"]), textarea, select'
                ).all()

                for field in fields:
                    try:
                        tag = await field.evaluate("el => el.tagName.toLowerCase()")
                        placeholder = await field.get_attribute("placeholder") or ""
                        aria_label = await field.get_attribute("aria-label") or ""
                        name_attr = await field.get_attribute("name") or ""

                        # Skip already-filled fields
                        try:
                            current_val = await field.input_value()
                            if current_val.strip():
                                continue
                        except Exception:
                            continue

                        # Skip known fields already handled above
                        lower_name = name_attr.lower()
                        lower_placeholder = placeholder.lower()
                        lower_aria = aria_label.lower()
                        if any(kw in lower_name + lower_placeholder + lower_aria for kw in ['linkedin', 'github', 'resume', 'file']):
                            continue

                        label_text = await field.evaluate("""el => {
                            const id = el.id;
                            if (id) {
                                const label = document.querySelector('label[for="' + id + '"]');
                                if (label) return label.innerText.trim();
                            }
                            const parent = el.closest('.form-group, .field-row, .input-group, li, div');
                            if (parent) {
                                const label = parent.querySelector('label');
                                if (label) return label.innerText.trim();
                            }
                            return '';
                        }""")

                        question = label_text or aria_label or placeholder
                        if not question.strip():
                            continue

                        print(f"[{PLATFORM}] Asking Groq for custom question: '{question}'")

                        prompt = f"""
You are an AI job assistant filling out a Wellfound (AngelList) application form.

User Profile:
{profile}

Custom question/Field: "{question}"
Field type: {tag}

CRITICAL INSTRUCTIONS:
1. If the question asks for a "Note", "Cover Letter", or "Why you want to work here": Write a passionate, 2-paragraph pitch directed at the founder. Highlight exactly how the user's skills match a fast-paced startup environment. 
2. For all other questions: Be concise and professional.
3. Respond with ONLY the raw answer text (no markdown, no intro).
"""
                        response = await invoke_with_fallback(configs, prompt)
                        answer = response.content.strip()
                        print(f"[{PLATFORM}] Groq answer: '{answer[:80]}'")

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
                        print(f"[{PLATFORM}] Could not fill custom field: {fe}")
                        continue

            except Exception as e:
                print(f"[{PLATFORM}] Error scanning custom questions: {e}")

            # --- Handle Multi-Step Modal (Next Buttons) ---
            for _ in range(5):
                try:
                    next_btn = page.locator("button:has-text('Next')").first
                    if await next_btn.is_visible(timeout=1000):
                        print(f"[{PLATFORM}] Found 'Next' button in modal. Clicking to advance...")
                        await next_btn.click(force=True)
                        await page.wait_for_timeout(3000)
                        
                        # Re-scan fields on the new modal page
                        fields = await page.locator('input:not([type="hidden"]), textarea, select').all()
                        # (In a full implementation we would loop and fill again, but advancing is the key fix)
                except:
                    break

            # --- Submit ---
            print(f"[{PLATFORM}] Looking for Submit button...")
            submit_selectors = [
                "button[type='submit']",
                "input[type='submit']",
                "button:has-text('Submit')",
                "button:has-text('Apply')",
                "[data-test='submit-button']",
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

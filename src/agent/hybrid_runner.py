import asyncio
import sqlite3
import os
import sys
import argparse

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from playwright.async_api import async_playwright
from langchain_openai import ChatOpenAI
from src.core.crud import get_all_llm_configs

def get_active_llm():
    configs = get_all_llm_configs()
    active = [c for c in configs if c.get('is_active')]
    active.sort(key=lambda x: x.get('priority', 99))
    if not active:
        raise ValueError("No active LLM found in database.")
    
    best = active[0]
    return ChatOpenAI(
        model=best['model_name'],
        api_key=best['api_key'],
        base_url="https://api.groq.com/openai/v1" if best['provider'] == 'groq' else None,
        temperature=0.2,
        max_tokens=500 # Restrict output tokens so Groq's free tier doesn't reject it for OTPM limits
    )

async def apply_to_job(url: str, no_ai: bool = False):
    if not no_ai:
        llm = get_active_llm()
    
    print("\n[Hybrid Mode] Initializing Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False) # Keep visible for user to see
        state_path = "storageState.json"
        
        if os.path.exists(state_path):
            context = await browser.new_context(storage_state=state_path)
            print("[Hybrid Mode] Loaded existing LinkedIn session.")
        else:
            context = await browser.new_context()
            print("[Hybrid Mode] WARNING: No session found. You may need to log in.")
            
        page = await context.new_page()
        
        print(f"[Hybrid Mode] Navigating to: {url}")
        await page.goto(url)
        await page.wait_for_timeout(3000)
        
        # Check for budget exhausted / closed
        if "BUDGET_EXHAUSTED" in url or "closed" in await page.content():
            print("[Hybrid Mode] WARNING: Job appears to be closed or budget exhausted.")
            
        if not no_ai:
            print("[Hybrid Mode] Reading Job Description...")
            try:
                job_description = await page.evaluate("document.body.innerText")
                job_description = job_description[:5000] # Truncate to save tokens
                print(f"[Hybrid Mode] Extracted {len(job_description)} characters of page text.")
            except Exception as e:
                print(f"[Hybrid Mode] Error reading page: {e}")
                job_description = ""
                
            if job_description:
                print("[Hybrid Mode] Asking AI to evaluate the job...")
                prompt = f"""
You are an expert career agent. Based on this job description:
1. Provide a 1-sentence summary of the role.
2. Write a 3-sentence cover letter matching a Junior Software Engineer (Python/React) to this role.
3. Does this role seem to support 'Easy Apply'? (Yes/No)

Job Description:
{job_description[:4000]}
"""
                response = await asyncio.to_thread(llm.invoke, prompt)
                print("\n================ AI EVALUATION ================")
                print(response.content)
                print("===============================================\n")
        else:
            print("[Hybrid Mode] Skipping AI evaluation (--no-ai flag active).")
            
        print("[Hybrid Mode] Attempting to find and click 'Easy Apply'...")
        try:
            modal_opened = False
            for click_attempt in range(4):
                # Use Javascript with getBoundingClientRect to find the visibly rendered button on the screen,
                # then use Playwright's native CDP click to dispatch a trusted MouseEvent that React will process.
                btn_handle = await page.evaluate_handle("""
                () => {
                    const elements = Array.from(document.querySelectorAll('*'));
                    return elements.find(el => {
                        const hasText = el.innerText && el.innerText.trim() === 'Easy Apply';
                        const hasClass = el.classList && el.classList.contains('jobs-apply-button');
                        if (!hasText && !hasClass) return false;
                        
                        // Verify it's actually rendered on screen (width/height > 0)
                        const rect = el.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 && el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE';
                    }) || null;
                }
                """)
                
                # Check if the handle points to an actual element
                is_valid_node = await btn_handle.evaluate("node => node !== null")
                
                if is_valid_node:
                    print(f"[Hybrid Mode] Click attempt {click_attempt + 1} sent to visually confirmed 'Easy Apply' button via CDP...")
                    # Native Playwright CDP click (Trusted Event) - force=True bypasses Playwright's strict visibility bounding rules
                    await btn_handle.click(force=True)
                    await page.wait_for_timeout(3000) # Wait for React to render modal
                else:
                    print(f"[Hybrid Mode] Click attempt {click_attempt + 1} failed: Could not find visible button.")

                # Verify modal actually opened by waiting for the modal container to render
                # This handles slow network connections where the modal takes a few seconds to appear
                modal_locator = page.locator(".artdeco-modal, div[role='dialog']").first
                try:
                    await modal_locator.wait_for(state="visible", timeout=8000)
                    print("[Hybrid Mode] SUCCESS: Modal is visually confirmed open!")
                    modal_opened = True
                    break
                except Exception:
                    print("[Hybrid Mode] Modal did not appear within 8 seconds. Retrying click...")
                    await page.wait_for_timeout(2000)
                    
            if not modal_opened:
                print("[Hybrid Mode] FAILED: Could not open the Easy Apply modal after 4 attempts.")
                
        except Exception as e:
            print(f"[Hybrid Mode] Error during click phase: {e}")
            
        if modal_opened:
            print("[Hybrid Mode] Scanning form steps...")
            for step in range(15): # Max 15 steps to prevent infinite loops while allowing long forms
                # Hover over the modal and scroll down forcefully using raw mouse events
                # This guarantees we scroll the modal even if the CSS classes change, forcing React to render the submit button
                try:
                    modal_box = page.locator(".artdeco-modal, div[role='dialog']").first
                    await modal_box.hover()
                    await page.mouse.wheel(0, 2000)
                    await page.wait_for_timeout(1000) # Wait for React virtualized scrolling to render the button
                except Exception:
                    pass

                # Use Playwright's native text locators restricted to the modal to find the buttons
                # text=/.../i is a case-insensitive regex search that checks textContent, value, and aria-labels across ALL elements!
                modal = page.locator(".artdeco-modal, div[role='dialog']").first
                
                submit_btn = modal.locator("text=/Submit application/i").first
                review_btn = modal.locator("button:has-text('Review'), [role='button']:has-text('Review')").first
                next_btn = modal.locator("button:has-text('Next'), [role='button']:has-text('Next')").first
                
                # Check for form validation errors (e.g. unanswered custom questions)
                if await modal.locator(".artdeco-inline-feedback--error, [role='alert']").first.is_visible():
                    print("\n[Hybrid Mode] Form validation error detected.")
                    
                    resolved_by_ai = False
                    if not no_ai:
                        for attempt in range(2):
                            print(f"[Hybrid Mode] Sniper AI: Attempting to solve question automatically (Attempt {attempt+1}/2)...")
                            try:
                                # 1. Extract the questions causing errors and inject unique IDs
                                # ULTIMATE FIX: We use Playwright's native locator to find the elements (piercing Shadow DOMs)
                                # and pass them directly into Javascript as an array of elements.
                                error_locators = modal.locator(".artdeco-inline-feedback--error, [role='alert']")
                                error_data = await error_locators.evaluate_all("""
                                (elements) => {
                                    const data = [];
                                    for (const err of elements) {
                                        // 1. Find the closest logical container for this form field
                                        let container = err.closest('.jobs-easy-apply-formElement, .jobs-easy-apply-form-section__item, fieldset, .fb-dash-form-element, [data-test-form-element]');
                                        
                                        // Fallback if no known classes match: just go up 1 or 2 levels
                                        if (!container) container = err.parentElement.parentElement;
                                        if (!container) container = err.parentElement;
                                        
                                        if (!container) continue;
                                        
                                        // 2. Extract Question Text (Tag-Agnostic)
                                        let questionText = "";
                                        const labelEl = container.querySelector('label, legend');
                                        
                                        if (labelEl) {
                                            questionText = labelEl.innerText;
                                        } else {
                                            // If no semantic label exists, grab the first line of visible text in the container
                                            // that isn't the error message itself
                                            const allText = container.innerText.split('\\n')
                                                .map(s => s.trim())
                                                .filter(s => s.length > 0 && !err.innerText.includes(s));
                                            if (allText.length > 0) {
                                                questionText = allText[0];
                                            }
                                        }
                                        
                                        if (questionText) {
                                            const selectEl = container.querySelector('select');
                                            const isSelect = selectEl !== null;
                                            const isCustomSelect = container.querySelector('button') !== null;
                                            const qType = (isSelect || isCustomSelect) ? 'dropdown' : 'input';
                                            
                                            let availableOptions = [];
                                            if (isSelect) {
                                                availableOptions = Array.from(selectEl.options).map(o => o.text.trim()).filter(t => t && !t.toLowerCase().includes('select'));
                                            }
                                            
                                            // Inject unique sniper ID into the DOM
                                            const sniperId = "sniper_" + Math.random().toString(36).substr(2, 9);
                                            container.setAttribute("data-sniper-id", sniperId);
                                            
                                            data.push({
                                                label: questionText.replace(/\\n/g, ' ').trim(), 
                                                type: qType, 
                                                sniper_id: sniperId,
                                                options: availableOptions,
                                                validation_error: err.innerText.replace(/\\n/g, ' ').trim()
                                            });
                                        }
                                    }
                                    return data;
                                }
                                """)
                                
                                if error_data:
                                    print(f"[Hybrid Mode] Sniper AI Extracted Questions: {error_data}")
                                    # 2. Ask Groq for the answers
                                    from src.core.crud import get_user_profile
                                    profile = get_user_profile() or {}
                                    
                                    prompt = f"""
                                    You are an AI job assistant. The application form requires answers for these questions:
                                    {error_data}
                                    
                                    User Profile Details:
                                    {profile}
                                    
                                    Respond in STRICT JSON format (no markdown code blocks, just raw JSON).
                                    Format:
                                    {{"answers": [{{"sniper_id": "the exact sniper_id from the question", "value": "your answer"}}]}}
                                    
                                    CRITICAL RULE: You MUST aggressively guess an answer for EVERY SINGLE QUESTION provided. Do NOT leave any question blank. 
                                    - If asked for years of experience, guess "0" if unknown. 
                                    - If asked a yes/no question, guess "Yes" if unknown.
                                    - If asked for CTC/Salary, guess "0" if unknown.
                                    - If asked for notice period, guess "0" if unknown.
                                    - If asked for location, guess from profile or "New Delhi" if unknown.
                                    - If "options" are provided for a dropdown, your value MUST exactly match one of the options.
                                    - If "validation_error" is provided, your previous guess was REJECTED by the system! You MUST adjust your guess to satisfy the validation_error rule (e.g. if the error says 'larger than 100', output '200000').
                                    """
                                    response = await asyncio.to_thread(llm.invoke, prompt)
                                    
                                    # 3. Parse and Execute
                                    import json
                                    try:
                                        # Clean json output
                                        raw_text = response.content.strip()
                                        print(f"[Hybrid Mode] Sniper AI Raw Response: {raw_text}")
                                        if raw_text.startswith("```json"): raw_text = raw_text[7:]
                                        if raw_text.startswith("```"): raw_text = raw_text[3:]
                                        if raw_text.endswith("```"): raw_text = raw_text[:-3]
                                        
                                        result = json.loads(raw_text.strip())
                                        for answer in result.get("answers", []):
                                            sniper_id = answer.get("sniper_id")
                                            q_value = str(answer.get("value"))
                                            print(f"[Hybrid Mode] Sniper AI Answering Target '{sniper_id}' -> '{q_value}'")
                                            
                                            # Locate the field container using the injected ID!
                                            container = page.locator(f"[data-sniper-id='{sniper_id}']")
                                            
                                            if await container.locator("input[type='text'], input[type='number'], textarea").count() > 0:
                                                input_el = container.locator("input[type='text'], input[type='number'], textarea").first
                                                await input_el.fill(q_value)
                                                await page.wait_for_timeout(1000)
                                                await input_el.press("ArrowDown")
                                                await input_el.press("Enter")
                                            elif await container.locator("input").count() > 0 and await container.locator("input").first.get_attribute("type") == "text":
                                                input_el = container.locator("input").first
                                                await input_el.fill(q_value)
                                                await page.wait_for_timeout(1000)
                                                await input_el.press("ArrowDown")
                                                await input_el.press("Enter")
                                            elif await container.locator("select").count() > 0:
                                                try:
                                                    await container.locator("select").first.select_option(label=q_value, timeout=2000)
                                                except Exception:
                                                    print(f"[Hybrid Mode] AI answer '{q_value}' not in dropdown. Forcing index 1 fallback.")
                                                    await container.locator("select").first.select_option(index=1, timeout=2000)
                                            elif await container.locator("button").count() > 0:
                                                # Custom LinkedIn Dropdown
                                                await container.locator("button").first.click(force=True)
                                                await page.wait_for_timeout(500)
                                                # Target the dropdown option across the whole page (often appended to body)
                                                await page.locator(f"div[role='option']:has-text('{q_value}'), li:has-text('{q_value}')").last.click(force=True)
                                            elif await container.locator(f"label:has-text('{q_value}')").count() > 0:
                                                # Radio buttons
                                                await container.locator(f"label:has-text('{q_value}')").first.click(force=True)
                                                
                                        await page.wait_for_timeout(1000)
                                        # Click next again
                                        if await review_btn.is_visible(): await review_btn.click(force=True)
                                        elif await next_btn.is_visible(): await next_btn.click(force=True)
                                        await page.wait_for_timeout(2000)
                                        
                                        # If the error is gone, we resolved it!
                                        if not await modal.locator(".artdeco-inline-feedback--error, [role='alert']").first.is_visible():
                                            resolved_by_ai = True
                                            print("[Hybrid Mode] Sniper AI successfully bypassed the question!")
                                            break # Break out of attempt loop
                                    except Exception as e:
                                        print(f"[Hybrid Mode] Sniper AI failed to parse/execute: {e}")
                                else:
                                    break # No error data extracted
                            except Exception as e:
                                print(f"[Hybrid Mode] Sniper AI encountered an error: {e}")

                    # Fallback to Smart Pause if AI was off or failed
                    if not resolved_by_ai:
                        print(f"\n[Hybrid Mode] ACTION REQUIRED: The form requires manual input (Custom Questions).")
                        print("[Hybrid Mode] You have 10 MINUTES to answer the questions on the screen and click 'Next' yourself.")
                        print("[Hybrid Mode] I will wait here until you progress to the next screen...\n")
                        # Wait until the error disappears (meaning the user answered and clicked next)
                        try:
                            await modal.locator(".artdeco-inline-feedback--error, [role='alert']").first.wait_for(state="hidden", timeout=600000)
                            print("[Hybrid Mode] Manual input detected! Resuming automation...")
                            await page.wait_for_timeout(2000)
                            continue # Restart the loop for the new screen
                        except Exception:
                            print("[Hybrid Mode] Manual intervention timed out. Proceeding to next step anyway...")
                            break
                
                if await submit_btn.is_visible():
                    print("[Hybrid Mode] SUCCESS: Reached the final 'Submit application' screen!")
                    print(f"[Hybrid Mode] Step {step+1}: Clicking 'Submit application'...")
                    await submit_btn.click(force=True)
                    await page.wait_for_timeout(3000)
                    print("[Hybrid Mode] Application submitted successfully!")
                    break
                elif await review_btn.is_visible():
                    print(f"[Hybrid Mode] Step {step+1}: Found 'Review' button. Clicking...")
                    await review_btn.click(force=True)
                    await page.wait_for_timeout(2000)
                elif await next_btn.is_visible():
                    print(f"[Hybrid Mode] Step {step+1}: Found 'Next' button. Clicking...")
                    await next_btn.click(force=True)
                    await page.wait_for_timeout(2000)
                else:
                    print("[Hybrid Mode] Waiting for form content to load or unknown button state...")
                    await page.wait_for_timeout(2000)
            
        print("[Hybrid Mode] Automation complete. Keeping browser open for 5 seconds for review...")
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="LinkedIn Job URL")
    parser.add_argument("--no-ai", action="store_true", help="Run without any LLM evaluation (Option 2)")
    args = parser.parse_args()
    
    asyncio.run(apply_to_job(args.url, args.no_ai))

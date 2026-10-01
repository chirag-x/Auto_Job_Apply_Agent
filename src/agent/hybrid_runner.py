import asyncio
import sqlite3
import os
import sys
import argparse

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from playwright.async_api import async_playwright
from src.agent.langchain_llm import build_llm
from src.core.crud import get_all_llm_configs

def get_active_llm():
    configs = get_all_llm_configs()
    active = [c for c in configs if c.get('is_active')]
    active.sort(key=lambda x: x.get('priority', 99))
    if not active:
        raise ValueError("No active LLM found in database.")
    
    best = active[0]
    return build_llm(best, temperature=0.2, max_tokens=500)

async def apply_to_job(url: str, no_ai: bool = False, headless: bool = False):
    if not no_ai:
        llm = get_active_llm()
    
    print("\n[Hybrid Mode] Initializing Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless) # Use the global headless toggle
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

                # Verify modal actually opened by waiting for a core form element
                # This handles slow network connections and avoids strict CSS class dependency
                modal_locator = page.locator(".artdeco-modal, div[role='dialog'], button:has-text('Next'), button:has-text('Submit'), button:has-text('Review')").first
                try:
                    await modal_locator.wait_for(state="attached", timeout=8000)
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
            for step in range(15):
                await page.wait_for_timeout(1500)
                modal = page.locator(".artdeco-modal, div[role='dialog']").first

                # === DEBUG: Dump actual radio fieldset HTML to understand LinkedIn's structure ===
                radio_html = await page.evaluate("""
                () => {
                    const container = document.querySelector('.artdeco-modal, [role="dialog"]') || document.body;
                    const fieldsets = container.querySelectorAll('fieldset');
                    if (fieldsets.length === 0) return 'NO_FIELDSETS';
                    return Array.from(fieldsets).slice(0, 2).map(f => f.outerHTML.substring(0, 600)).join('\\n---\\n');
                }
                """)
                print(f"[DEBUG Radio HTML]\\n{radio_html}\\n[/DEBUG]", flush=True)


                empty_fields = await page.evaluate("""
                () => {
                    let container = document.querySelector('.artdeco-modal')
                        || document.querySelector('.jobs-easy-apply-modal')
                        || document.querySelector('[role="dialog"]')
                        || document.body;

                    const SKIP_TEXTS = ['additional questions', 'contact info', 'resume', 'work experience', 'education'];
                    const fields = [];

                    // Helper: get question text for an input - checks label[for], aria-label, then nearby siblings
                    function getLabel(el) {
                        if (el.id) {
                            const lbl = document.querySelector(`label[for="${el.id}"]`);
                            if (lbl) return lbl.innerText.trim();
                        }
                        const aria = el.getAttribute('aria-label') || el.getAttribute('aria-labelledby');
                        if (aria) {
                            const ref = document.getElementById(aria);
                            return ref ? ref.innerText.trim() : aria;
                        }
                        // Walk up max 3 levels, look for the FIRST label/legend that's not generic
                        let p = el.parentElement;
                        for (let i = 0; i < 3; i++) {
                            if (!p) break;
                            const candidates = p.querySelectorAll('label, legend, span[class*="label"]');
                            for (const c of candidates) {
                                if (c.contains(el)) continue;
                                const t = c.innerText.trim().replace(/\\*/g, '').trim();
                                if (t.length > 5 && !SKIP_TEXTS.some(s => t.toLowerCase().startsWith(s))) return t;
                            }
                            p = p.parentElement;
                        }
                        return el.placeholder || el.name || 'field';
                    }

                    // Helper: get question for a FIELDSET (radio group) - look at siblings BEFORE it
                    function getFieldsetLabel(fieldset) {
                        // Check immediate previous siblings in the same parent
                        const parent = fieldset.parentElement;
                        if (parent) {
                            let sib = fieldset.previousElementSibling;
                            while (sib) {
                                const t = sib.innerText ? sib.innerText.trim().replace(/\\*/g, '').trim() : '';
                                if (t.length > 8 && !SKIP_TEXTS.some(s => t.toLowerCase().startsWith(s))) return t;
                                sib = sib.previousElementSibling;
                            }
                        }
                        // Go up one level and check that parent's previous siblings
                        const grandparent = fieldset.parentElement?.parentElement;
                        if (grandparent) {
                            let sib = fieldset.parentElement.previousElementSibling;
                            while (sib) {
                                const t = sib.innerText ? sib.innerText.trim().replace(/\\*/g, '').trim() : '';
                                if (t.length > 8 && !SKIP_TEXTS.some(s => t.toLowerCase().startsWith(s))) return t;
                                sib = sib.previousElementSibling;
                            }
                        }
                        // Last resort: legend text
                        const legend = fieldset.querySelector('legend');
                        if (legend) {
                            const t = legend.innerText.trim().replace(/\\*/g, '').trim();
                            if (t.length > 5 && !SKIP_TEXTS.some(s => t.toLowerCase().startsWith(s))) return t;
                        }
                        return 'Yes/No question';
                    }

                    // --- Text / Number / Textarea / Select ---
                    const inputs = container.querySelectorAll(
                        'input:not([type="radio"]):not([type="checkbox"]):not([type="file"]):not([type="hidden"]):not([type="submit"]), textarea, select'
                    );
                    for (const input of inputs) {
                        const isRequired = input.required || input.getAttribute('aria-required') === 'true';
                        const isEmpty = !input.value || input.value.trim() === '';
                        const isInvalid = input.getAttribute('aria-invalid') === 'true';
                        if (!((isRequired && isEmpty) || isInvalid)) continue;
                        const label = getLabel(input).replace(/\\n/g, ' ').trim();
                        const sniperId = 'inp_' + Math.random().toString(36).substr(2, 9);
                        input.setAttribute('data-sniper-id', sniperId);
                        fields.push({ label, type: input.tagName.toLowerCase() === 'select' ? 'dropdown' : 'input', sniper_id: sniperId, input_type: input.type || 'text' });
                    }

                    // --- Radio groups ---
                    const fieldsets = container.querySelectorAll('fieldset');
                    for (const fieldset of fieldsets) {
                        const radios = Array.from(fieldset.querySelectorAll('input[type="radio"]'));
                        if (radios.length === 0 || radios.some(r => r.checked)) continue;
                        const questionText = getFieldsetLabel(fieldset);
                        const options = radios.map(r => {
                            const lbl = document.querySelector(`label[for="${r.id}"]`) || r.parentElement;
                            return lbl ? lbl.innerText.trim() : r.value;
                        }).filter(Boolean);
                        const sniperId = 'radio_' + Math.random().toString(36).substr(2, 9);
                        fieldset.setAttribute('data-sniper-id', sniperId);
                        fields.push({ label: questionText.replace(/\\n/g, ' ').trim(), type: 'radio', sniper_id: sniperId, options });
                    }

                    return fields;
                }
                """)

                if empty_fields and not no_ai:
                    print(f"[Hybrid Mode] Proactive Fill: Found {len(empty_fields)} fields: {[f['label'][:50] for f in empty_fields]}")
                    from src.core.crud import get_user_profile
                    profile = get_user_profile() or {}

                    prompt = f"""You are a job application bot. Fill these form fields from the user's profile.

Fields:
{empty_fields}

User Profile:
{profile}

RULES:
- "year"/"experience" field → NUMBER only (e.g. "0", "1"). NEVER a name.
- radio type → value MUST exactly match one of the "options" list
- Any Yes/No question → "Yes"
- Phone → profile phone or "8305525932"
- Country code → "India (+91)"
- Salary → "0"
- Location → profile location or "Gwalior, Madhya Pradesh"

Return ONLY raw JSON: {{"answers": [{{"sniper_id": "id", "value": "answer"}}]}}"""

                    try:
                        import json
                        response = await asyncio.to_thread(llm.invoke, prompt)
                        raw = response.content.strip()
                        if raw.startswith("```"): raw = raw.split("```")[1]
                        if raw.startswith("json"): raw = raw[4:]
                        result = json.loads(raw.strip())

                        for answer in result.get("answers", []):
                            sniper_id = answer.get("sniper_id", "")
                            q_value = str(answer.get("value", "")).strip()
                            if not q_value or not sniper_id:
                                continue
                            print(f"[Hybrid Mode] Fill: '{sniper_id}' -> '{q_value}'")

                            target = page.locator(f"[data-sniper-id='{sniper_id}']")
                            if await target.count() == 0:
                                continue

                            tag = await target.evaluate("el => el.tagName.toLowerCase()")

                            if tag == "fieldset":
                                # LinkedIn uses custom styled radios: the <input> is visually hidden,
                                # the real clickable target is <label for="radioId"> (the text label)
                                radio_inputs = target.locator('input[type="radio"]')
                                count = await radio_inputs.count()
                                clicked = False
                                for i in range(count):
                                    radio = radio_inputs.nth(i)
                                    radio_id = await radio.get_attribute("id") or ""
                                    if not radio_id:
                                        continue
                                    # Get the small label element that says "Yes" / "No"
                                    lbl = page.locator(f'label[for="{radio_id}"]').first
                                    if await lbl.count() == 0:
                                        continue
                                    label_text = (await lbl.inner_text()).strip()
                                    if q_value.lower() in label_text.lower() or label_text.lower() in q_value.lower():
                                        await lbl.scroll_into_view_if_needed()
                                        await lbl.click()  # Click the LABEL text, not the hidden input
                                        await page.wait_for_timeout(400)
                                        clicked = True
                                        print(f"[Hybrid Mode] Radio: clicked label '{label_text}'")
                                        break
                                if not clicked and count > 0:
                                    # Fallback: click first option's label
                                    first_id = await radio_inputs.first.get_attribute("id") or ""
                                    if first_id:
                                        first_lbl = page.locator(f'label[for="{first_id}"]').first
                                        if await first_lbl.count() > 0:
                                            await first_lbl.scroll_into_view_if_needed()
                                            await first_lbl.click()
                                            print(f"[Hybrid Mode] Radio fallback: clicked first label")

                            elif tag == "select":
                                try:
                                    await target.select_option(label=q_value, timeout=2000)
                                except:
                                    await target.select_option(index=1, timeout=2000)
                            elif tag in ("input", "textarea"):
                                await target.click()
                                await target.fill("")
                                await target.type(q_value, delay=30)
                                await page.wait_for_timeout(300)

                        await page.wait_for_timeout(800)
                    except Exception as fill_err:
                        print(f"[Hybrid Mode] Proactive Fill error: {fill_err}")



                # === STEP 2: NAVIGATE (scroll + check errors + click Next/Review/Submit) ===
                btn_result = await page.evaluate("""
                () => {
                    // LinkedIn uses multiple modal patterns - try all of them
                    let modal = document.querySelector('.artdeco-modal')
                        || document.querySelector('.jobs-easy-apply-modal')
                        || document.querySelector('[class*="easy-apply-modal"]')
                        || document.querySelector('[role="dialog"]')
                        || document.querySelector('[class*="application-form"]');

                    const container = modal || document.body;

                    // Scroll down to reveal hidden buttons
                    if (modal) {
                        const scrollTarget = modal.querySelector('[class*="content"], [class*="body"], [class*="scroll"]') || modal;
                        scrollTarget.scrollTop = scrollTarget.scrollHeight;
                    } else {
                        window.scrollTo(0, document.body.scrollHeight);
                    }

                    const buttons = Array.from(container.querySelectorAll('button'));
                    
                    // Check for validation errors using ALL LinkedIn error patterns
                    const errors = container.querySelectorAll(
                        '.artdeco-inline-feedback--error, [class*="inline-feedback--error"], [aria-invalid="true"], [class*="error-msg"], [class*="validation-error"]'
                    );
                    // Also check for any visible red text (aria-invalid inputs create sibling error spans)
                    const invalidInputs = container.querySelectorAll('input[aria-invalid="true"], textarea[aria-invalid="true"]');
                    if (errors.length > 0 || invalidInputs.length > 0) return 'has_errors';

                    // Priority 1: Submit
                    const submitBtn = buttons.find(b => b.innerText.trim().toLowerCase().includes('submit application'));
                    if (submitBtn && !submitBtn.disabled) { submitBtn.click(); return 'submit'; }

                    // Priority 2: Review
                    const reviewBtn = buttons.find(b => b.innerText.trim().toLowerCase() === 'review');
                    if (reviewBtn && !reviewBtn.disabled) { reviewBtn.click(); return 'review'; }

                    // Priority 3: Next
                    const nextBtn = buttons.find(b => b.innerText.trim().toLowerCase() === 'next');
                    if (nextBtn && !nextBtn.disabled) { nextBtn.click(); return 'next'; }

                    if (modal) return 'waiting_modal_' + (modal.className || 'no_class').substring(0, 50);
                    return 'no_content';
                }
                """)



                print(f"[Hybrid Mode] Step {step+1}: Nav result = '{btn_result}'", flush=True)

                if btn_result == 'submit':
                    print("[Hybrid Mode] SUCCESS: Reached the final 'Submit application' screen!")
                    await page.wait_for_timeout(3000)
                    print("[Hybrid Mode] Application submitted successfully!")
                    break
                elif btn_result in ('review', 'next'):
                    print(f"[Hybrid Mode] Step {step+1}: Clicked '{btn_result}'. Moving to next step...")
                    await page.wait_for_timeout(2500)
                elif btn_result == 'no_content':
                    print("[Hybrid Mode] No form content or buttons found. Application may have redirected externally. Done.")
                    break

                elif btn_result == 'has_errors':
                    print("\n[Hybrid Mode] Form validation error detected. Running Sniper AI...")
                    resolved_by_ai = False
                    if not no_ai:
                        for attempt in range(2):
                            print(f"[Hybrid Mode] Sniper AI: Attempt {attempt+1}/2...")
                            try:
                                error_locators = modal.locator(".artdeco-inline-feedback--error, [role='alert']")
                                error_data = await error_locators.evaluate_all("""
                                (elements) => {
                                    const data = [];
                                    for (const err of elements) {
                                        let container = err.closest('.jobs-easy-apply-formElement, .jobs-easy-apply-form-section__item, fieldset, .fb-dash-form-element, [data-test-form-element]');
                                        if (!container) container = err.parentElement.parentElement;
                                        if (!container) container = err.parentElement;
                                        if (!container) continue;
                                        let questionText = "";
                                        const labelEl = container.querySelector('label, legend');
                                        if (labelEl) { questionText = labelEl.innerText; }
                                        else {
                                            const allText = container.innerText.split('\\n').map(s => s.trim()).filter(s => s.length > 0 && !err.innerText.includes(s));
                                            if (allText.length > 0) questionText = allText[0];
                                        }
                                        if (questionText) {
                                            const selectEl = container.querySelector('select');
                                            const isSelect = selectEl !== null;
                                            const qType = isSelect ? 'dropdown' : 'input';
                                            let availableOptions = [];
                                            if (isSelect) availableOptions = Array.from(selectEl.options).map(o => o.text.trim()).filter(t => t && !t.toLowerCase().includes('select'));
                                            const sniperId = "sniper_" + Math.random().toString(36).substr(2, 9);
                                            container.setAttribute("data-sniper-id", sniperId);
                                            data.push({ label: questionText.replace(/\\n/g, ' ').trim(), type: qType, sniper_id: sniperId, options: availableOptions, validation_error: err.innerText.replace(/\\n/g, ' ').trim() });
                                        }
                                    }
                                    return data;
                                }
                                """)
                                if error_data:
                                    print(f"[Hybrid Mode] Sniper AI Questions: {error_data}")
                                    from src.core.crud import get_user_profile
                                    profile = get_user_profile() or {}
                                    prompt = f"""You are an AI job assistant. The application form requires answers for these questions: {error_data}
User Profile: {profile}
Respond in STRICT JSON: {{"answers": [{{"sniper_id": "exact_id", "value": "your_answer"}}]}}
CRITICAL: Guess an answer for EVERY question. Never leave blank. For experience guess "0", for yes/no guess "Yes", for salary guess "0". Match dropdown options exactly."""
                                    response = await asyncio.to_thread(llm.invoke, prompt)
                                    import json
                                    try:
                                        raw_text = response.content.strip()
                                        print(f"[Hybrid Mode] Sniper AI Response: {raw_text}")
                                        if raw_text.startswith("```json"): raw_text = raw_text[7:]
                                        if raw_text.startswith("```"): raw_text = raw_text[3:]
                                        if raw_text.endswith("```"): raw_text = raw_text[:-3]
                                        result = json.loads(raw_text.strip())
                                        for answer in result.get("answers", []):
                                            sniper_id = answer.get("sniper_id")
                                            q_value = str(answer.get("value"))
                                            print(f"[Hybrid Mode] Answering '{sniper_id}' -> '{q_value}'")
                                            container = page.locator(f"[data-sniper-id='{sniper_id}']")
                                            if await container.locator("input[type='text'], input[type='number'], textarea").count() > 0:
                                                await container.locator("input[type='text'], input[type='number'], textarea").first.fill(q_value)
                                                await page.wait_for_timeout(500)
                                            elif await container.locator("select").count() > 0:
                                                try: await container.locator("select").first.select_option(label=q_value, timeout=2000)
                                                except: await container.locator("select").first.select_option(index=1, timeout=2000)
                                            elif await container.locator("button").count() > 0:
                                                await container.locator("button").first.click(force=True)
                                                await page.wait_for_timeout(500)
                                                await page.locator(f"div[role='option']:has-text('{q_value}'), li:has-text('{q_value}')").last.click(force=True)
                                            elif await container.locator(f"label:has-text('{q_value}')").count() > 0:
                                                await container.locator(f"label:has-text('{q_value}')").first.click(force=True)
                                        await page.wait_for_timeout(1000)
                                        # JS click next after filling
                                        await page.evaluate("""() => { const m = document.querySelector('.artdeco-modal, [role="dialog"]'); if(!m) return; const btns = Array.from(m.querySelectorAll('button')); const r = btns.find(b => b.innerText.trim().toLowerCase() === 'review'); const n = btns.find(b => b.innerText.trim().toLowerCase() === 'next'); if(r && !r.disabled) r.click(); else if(n && !n.disabled) n.click(); }""")
                                        await page.wait_for_timeout(2000)
                                        if not await modal.locator(".artdeco-inline-feedback--error, [role='alert']").first.is_visible():
                                            resolved_by_ai = True
                                            print("[Hybrid Mode] Sniper AI successfully resolved the question!")
                                            break
                                    except Exception as e:
                                        print(f"[Hybrid Mode] Sniper parse error: {e}")
                                else:
                                    break
                            except Exception as e:
                                print(f"[Hybrid Mode] Sniper error: {e}")
                    if not resolved_by_ai:
                        print("\n[Hybrid Mode] ACTION REQUIRED: Answer the questions manually. Waiting 10 min...")
                        try:
                            for _ in range(300):
                                if not await modal.locator(".artdeco-inline-feedback--error, [role='alert']").first.is_visible():
                                    break
                                await page.wait_for_timeout(2000)
                            print("[Hybrid Mode] Manual input detected! Resuming...")
                            await page.wait_for_timeout(2000)
                        except Exception:
                            break
                else:
                    print("[Hybrid Mode] Waiting for form to load...")
                    await page.wait_for_timeout(2000)
        print("[Hybrid Mode] Automation complete. Keeping browser open for 5 seconds for review...")
        await page.wait_for_timeout(3000)
        await browser.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True, help="LinkedIn Job URL")
    parser.add_argument("--no-ai", action="store_true", help="Run without any LLM evaluation (Option 2)")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode")
    args = parser.parse_args()
    
    asyncio.run(apply_to_job(args.url, args.no_ai, args.headless))

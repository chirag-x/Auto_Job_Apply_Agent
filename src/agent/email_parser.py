import imaplib
import email
from email.header import decode_header
import sqlite3
import os
import sys
import json
import asyncio
from datetime import datetime, timedelta

# Add project root to Python path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.core.db import get_db_connection
from src.core.crud import get_all_llm_configs, get_user_profile
from src.agent.langchain_llm import build_llm

def get_active_configs():
    configs = get_all_llm_configs()
    active = [c for c in configs if c.get('is_active')]
    active.sort(key=lambda x: x.get('priority', 99))
    if not active:
        raise ValueError("No active LLM found in database.")
    return active

async def invoke_with_fallback(configs, prompt, temperature=0.0):
    for best in configs:
        try:
            llm = build_llm(best, temperature=temperature)
            return await asyncio.to_thread(llm.invoke, prompt)
        except Exception as e:
            print(f"⚠️ Brain '{best.get('model_name')}' failed ({e}). Trying next...")
            continue
    raise Exception("All active brains failed.")

def clean_html(raw_html):
    import re
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, ' ', raw_html)
    return ' '.join(cleantext.split())

def decode_mime_header(header):
    if not header:
        return ""
    decoded_parts = decode_header(header)
    result = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            result += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            result += part
    return result

async def scan_emails():
    print("[Scanner] Starting autonomous email parser...")
    # 1. Get all credentials
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM email_credentials ORDER BY id ASC")
        all_creds = cursor.fetchall()
        
    if not all_creds:
        return {"success": False, "message": "No email credentials found. Please set them up in the Interview Tracker settings."}
        
    configs = get_active_configs()
    total_processed = 0
    total_updates = 0
    
    parsing_prompt = """
    You are an AI assistant parsing incoming emails for a job applicant.
    Determine if this email is a response to a job application or an application confirmation.
    
    Email Subject: {subject}
    Email Sender: {sender}
    Email Body excerpt: {body}
    
    Respond in JSON format ONLY:
    {{
        "status": "irrelevant" | "applied" | "interview_invite" | "rejected" | "assessment" | "offer",
        "company": "Extracted Company Name or null",
        "job_title": "Extracted Job Title or null",
        "notes": "Brief summary of the next steps or the rejection reason (max 1 sentence)"
    }}
    
    Rules:
    - If it's spam or unrelated, mark as "irrelevant".
    - If it is a confirmation that an application was just submitted, sent, or received (e.g., from LinkedIn, Indeed, Wellfound, Naukri, Internshala), mark as "applied".
    - If it asks for availability for a call, interview, or meeting, mark as "interview_invite".
    - If it gives a link to a HackerRank, take-home test, or assessment, mark as "assessment".
    - If it's a job offer, mark as "offer".
    - Extract company name carefully (e.g. from sender email domain or body).
    """
    
    for creds in all_creds:
        alias = creds['alias'] or "Main"
        imap_server = creds['imap_server']
        imap_port = creds['imap_port']
        email_address = creds['email_address']
        app_password = creds['app_password']
        last_scanned = creds['last_scanned_at']
        
        print(f"\n[Scanner] === Processing Account: {alias} ({email_address}) ===")
        print(f"[Scanner] Connecting to {imap_server}:{imap_port}...")
        
        try:
            mail = imaplib.IMAP4_SSL(imap_server, imap_port)
            mail.login(email_address, app_password)
            print(f"[Scanner] Authentication successful. Opening Inbox...")
            mail.select("inbox")
        except Exception as e:
            print(f"[Scanner] Error connecting to {alias}: {e}")
            continue
            
        import os, json
        uid_state_file = os.path.join(os.path.dirname(__file__), "last_uids.json")
        try:
            with open(uid_state_file, "r") as f:
                last_uids = json.load(f)
        except:
            last_uids = {}
            
        is_first_time = email_address not in last_uids
        last_uid = last_uids.get(email_address, 1)
        
        if is_first_time:
            print(f"[Scanner] First time scanning {alias}. Will fetch the last 50 emails to initialize memory.")
            status, messages = mail.uid('search', None, 'ALL')
        else:
            print(f"[Scanner] Resuming scan for {alias} from memory (UID > {last_uid})...")
            status, messages = mail.uid('search', None, f'UID {last_uid}:*')
            
        if status != "OK" or not messages[0]:
            print(f"[Scanner] No emails found for {alias}.")
            mail.logout()
            continue
            
        uids = messages[0].split()
        
        if is_first_time:
            uids = uids[-50:] # Cap at 50 for first time
        else:
            # Strictly filter new ones based on UID
            uids = [u for u in uids if int(u) > last_uid]
            
        if not uids:
            print(f"[Scanner] No strictly new emails found for {alias}. Already up to date.")
            mail.logout()
            continue
            
        print(f"[Scanner] Processing {len(uids)} new emails...")
        max_processed_uid = last_uid
        
        for e_uid in uids:
            max_processed_uid = max(max_processed_uid, int(e_uid))
            try:
                _, msg_data = mail.uid('fetch', e_uid, '(RFC822)')
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        subject = decode_mime_header(msg.get("Subject", ""))
                        sender = decode_mime_header(msg.get("From", ""))
                        
                        print(f"[Scanner] Analyzing: {subject[:50]}... from {sender[:30]}...")
                        search_str = f"{subject} {sender}".lower()
                        if not any(k in search_str for k in ["interview", "application", "applied", "update", "status", "assessment", "test", "candidate", "reject", "unfortunately", "offer", "next step", "career", "jobs"]):
                            print("  -> No interview keywords found. Skipping.")
                            continue
                            
                        body = ""
                        if msg.is_multipart():
                            for part in msg.walk():
                                content_type = part.get_content_type()
                                if "text/plain" in content_type:
                                    try:
                                        body += part.get_payload(decode=True).decode()
                                    except:
                                        pass
                                elif "text/html" in content_type and not body:
                                    try:
                                        html = part.get_payload(decode=True).decode()
                                        body += clean_html(html)
                                    except:
                                        pass
                        else:
                            try:
                                payload = msg.get_payload(decode=True)
                                if msg.get_content_type() == "text/html":
                                    body = clean_html(payload.decode())
                                else:
                                    body = payload.decode()
                            except:
                                pass
                                
                        body = body[:2000]
                        if not body.strip():
                            continue
                            
                        total_processed += 1
                        print(f"  -> Keywords matched! Asking LLM Brain to analyze intent...")
                        prompt = parsing_prompt.format(subject=subject, sender=sender, body=body)
                        
                        try:
                            llm_resp = await invoke_with_fallback(configs, prompt)
                            raw = llm_resp.content.strip().strip("```json").strip("```").strip()
                            data = json.loads(raw)
                            
                            if data.get("status") in ["applied", "interview_invite", "rejected", "assessment", "offer"] and data.get("company"):
                                company = data["company"].strip()
                                new_status = data["status"]
                                notes = data.get("notes", "")
                                
                                with get_db_connection() as conn:
                                    cur = conn.cursor()
                                    cur.execute("SELECT id FROM job_applications WHERE LOWER(company) LIKE ? ORDER BY applied_at DESC LIMIT 1", (f"%{company.lower()}%",))
                                    row = cur.fetchone()
                                    
                                    if row:
                                        print(f"  -> Brain matched: {company} is an active application. Updating status to: {new_status}!")
                                        cur.execute("UPDATE job_applications SET status = ?, logs = ?, email_alias = ? WHERE id = ?", (new_status, f"Email Update: {notes}", alias, row['id']))
                                        total_updates += 1
                                    else:
                                        print(f"  -> Brain matched: {company} (New Application). Auto-creating tracker entry with status: {new_status}!")
                                        cur.execute("""
                                            INSERT INTO job_applications (platform, job_id, job_title, company, status, logs, email_alias)
                                            VALUES (?, ?, ?, ?, ?, ?, ?)
                                        """, ("email", f"email_{e_id.decode()}", data.get("job_title") or "Unknown Role", company, new_status, f"Auto-created from email. {notes}", alias))
                                        total_updates += 1
                                    conn.commit()
                        except Exception as e:
                            print(f"  -> Error parsing email {e_id}: {e}")
            except Exception as e:
                print(f"[Scanner] Error fetching email: {e}")
                
        with get_db_connection() as conn:
            conn.cursor().execute("UPDATE email_credentials SET last_scanned_at = CURRENT_TIMESTAMP WHERE id = ?", (creds['id'],))
            conn.commit()
            
        print(f"[Scanner] Execution finished for {alias}. Closing connection.")
        mail.logout()
        
    return {"success": True, "message": "Scan complete.", "processed": total_processed, "updates": total_updates}

if __name__ == "__main__":
    res = asyncio.run(scan_emails())
    print("###FINAL_RESULT###" + json.dumps(res))

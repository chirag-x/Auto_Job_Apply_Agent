import asyncio
import sys
import os
import json
import codecs

if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.scrapers.linkedin_scraper import scrape_linkedin_jobs
from src.scrapers.naukri_scraper import scrape_naukri_jobs
from src.scrapers.internshala_scraper import scrape_internshala_jobs
from src.scrapers.wellfound_scraper import scrape_wellfound_jobs
from src.scrapers.indeed_scraper import scrape_indeed_jobs

def log_progress(msg, pct):
    print(f"{msg}", flush=True)

async def main():
    if len(sys.argv) < 2:
        print("Missing config file path")
        sys.exit(1)
        
    config_file = sys.argv[1]
    with open(config_file, 'r') as f:
        config = json.load(f)
        
    platforms = config.get("platforms", [])
    roles = config.get("roles", [])
    location = config.get("location", "India")
    start_offset = config.get("start_offset", 0)
    max_jobs = config.get("max_jobs", 10)
    match_threshold = config.get("match_threshold", 50)
    headless = config.get("headless", True)
    
    print(f"Starting Background Aggregator for roles: {roles} (Headless: {headless})", flush=True)
    
    for platform in platforms:
        print(f"--- Starting {platform.capitalize()} Sourcing ---", flush=True)
        try:
            if platform == "linkedin":
                await scrape_linkedin_jobs(roles, location, start_offset, max_jobs, match_threshold, log_progress, headless=headless)
            elif platform == "naukri":
                await scrape_naukri_jobs(roles, location, start_offset, max_jobs, match_threshold, log_progress, headless=headless)
            elif platform == "internshala":
                await scrape_internshala_jobs(roles, location, start_offset, max_jobs, match_threshold, log_progress, headless=headless)
            elif platform == "wellfound":
                await scrape_wellfound_jobs(roles, location, start_offset, max_jobs, match_threshold, log_progress, headless=headless)
            elif platform == "indeed":
                await scrape_indeed_jobs(roles, location, start_offset, max_jobs, match_threshold, log_progress, headless=headless)
        except Exception as e:
            print(f"Error scraping {platform}: {e}", flush=True)
            
    print("ALL DONE", flush=True)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from playwright.async_api import async_playwright
import os

async def record_session(platform_name: str, url: str, output_file: str):
    print(f"Launching browser for {platform_name} login...")
    async with async_playwright() as p:
        # We use the real Google Chrome channel and disable automation flags
        # to prevent Google SSO from blocking the login.
        browser = await p.chromium.launch(
            headless=False,
            channel="chrome",
            args=['--disable-blink-features=AutomationControlled'],
            ignore_default_args=["--enable-automation"]
        )
        context = await browser.new_context()
        page = await context.new_page()
        
        await page.goto(url)
        print(f"\n[{platform_name}] Please log in manually in the browser window.")
        print("Once you have successfully logged in, simply CLOSE the browser window.")
        
        # Wait until the user closes the page/browser manually
        try:
            await page.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
        print("\nBrowser closed. Saving session state...")
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        await context.storage_state(path=output_file)
        await browser.close()
        print(f"✅ Session saved successfully to {output_file}!")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--platform", default="linkedin", help="Name of the platform")
    parser.add_argument("--url", default="https://www.linkedin.com/login", help="Login URL")
    
    # Default to saving in the root directory
    default_output = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "storageState.json")
    parser.add_argument("--output", default=default_output, help="Path to save the state JSON")
    
    args = parser.parse_args()
    
    asyncio.run(record_session(args.platform, args.url, args.output))

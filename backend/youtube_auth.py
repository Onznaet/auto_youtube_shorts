import sys
import os
import time
from playwright.sync_api import sync_playwright

def main():
    if len(sys.argv) < 2:
        print("Usage: python youtube_auth.py <project_id>")
        sys.exit(1)

    project_id = sys.argv[1]
    
    # Path for storing persistent context
    base_dir = os.path.dirname(os.path.abspath(__file__))
    profiles_dir = os.path.join(base_dir, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    user_data_dir = os.path.join(profiles_dir, f"project_{project_id}")

    print(f"Launching browser for project {project_id}...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            # We don't use 'chrome' channel by default because we just installed the internal chromium.
            # But YouTube might block the internal chromium. We will try default first.
            args=[
                "--disable-blink-features=AutomationControlled",
            ]
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        
        try:
            page.goto("https://studio.youtube.com/")
        except Exception as e:
            print("Failed to navigate:", e)
        
        print("Browser opened. Please log in to YouTube.")
        print("When you are done, simply close the browser window.")
        
        try:
            # Wait until the user closes the page/browser
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
        print("Browser closed. Authentication completed.")

if __name__ == "__main__":
    main()

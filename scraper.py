import os
import sys
import time
from pathlib import Path

# --- CONFIGURATION ---
TARGET_WEBSITE = "https://example.com/infinite-gallery"
NETWORK_INTERCEPT_KEYWORD = "image-cdn"
DOWNLOAD_FOLDER_NAME = "ImageScraper"
ITEM_NAME = "image" # Used in logging (e.g. "Downloaded new image")
MAX_DUPLICATES = 10
IDLE_TIMEOUT_SECONDS = 5
# ---------------------

# Try importing playwright early so it fails fast if not installed
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("Playwright is not installed. Please run: pip install playwright && playwright install")
    sys.exit(1)

# Destination directory setup
DOWNLOAD_DIR = Path.home() / "Downloads" / DOWNLOAD_FOLDER_NAME

def run(playwright):
    print("Launching browser...")
    # Launch in headed mode with specific window size
    browser = playwright.chromium.launch(
        headless=False,
        args=['--window-size=776,984']
    )
    # create a context with the specific viewport size
    context = browser.new_context(viewport={"width": 776, "height": 984})
    page = context.new_page()
    
    # Create the download folder if it doesn't already exist
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Items will be downloaded to: {DOWNLOAD_DIR}")
    
    # Track downloaded files to avoid duplicates
    downloaded_files = set()
    for f in DOWNLOAD_DIR.iterdir():
        if f.is_file():
            downloaded_files.add(f.name)
            
    print(f"Found {len(downloaded_files)} previously downloaded files.")
            
    duplicates_in_a_row = 0
    max_duplicates = MAX_DUPLICATES
    downloaded_this_session = 0
    last_response_time = time.time()
    
    def handle_response(response):
        nonlocal duplicates_in_a_row
        nonlocal downloaded_this_session
        nonlocal last_response_time
        
        # We are looking for specific backend urls that fetch images
        if NETWORK_INTERCEPT_KEYWORD in response.url and response.request.resource_type == "image":
            last_response_time = time.time()
            # Extract filename from url
            filename = response.url.split("/")[-1].split("?")[0]
            
            # Ensure it has a png extension 
            if not filename.endswith(".png"):
                filename += ".png"
                
            if filename in downloaded_files:
                duplicates_in_a_row += 1
                if duplicates_in_a_row <= max_duplicates:
                    print(f"Duplicate detected: {filename} - This is duplicate {duplicates_in_a_row} out of {max_duplicates} in a row.")
            else:
                try:
                    # Download and save the image
                    body = response.body()
                    with open(DOWNLOAD_DIR / filename, "wb") as f:
                        f.write(body)
                        
                    downloaded_files.add(filename)
                    duplicates_in_a_row = 0 # reset duplicate counter
                    downloaded_this_session += 1
                    print(f"Downloaded new {ITEM_NAME}: {filename}")
                except Exception as e:
                    print(f"Failed to download {filename}: {e}")

    # Listen to response events
    page.on("response", handle_response)
    
    print(f"Navigating to target website: {TARGET_WEBSITE}")
    page.goto(TARGET_WEBSITE)
    
    # Wait a bit for initial load
    page.wait_for_timeout(3000)
    
    print("Beginning auto-scroll and listening for downloads...")
    try:
        while duplicates_in_a_row < max_duplicates:
            # Scroll down the page using javascript for guaranteed scrolling
            page.evaluate("window.scrollBy(0, 1500)")
            
            # Wait a bit
            page.wait_for_timeout(1000)
            
            # If no new relevant network requests have occurred in the last X seconds, close it
            if time.time() - last_response_time > IDLE_TIMEOUT_SECONDS:
                print(f"\nNetwork idle timeout reached ({IDLE_TIMEOUT_SECONDS}s). No new requests detected. Stopping...")
                break
                
    except KeyboardInterrupt:
        print("\nStopped by user (Ctrl+C).")
        
    print("\nStopping script...")
    if duplicates_in_a_row >= max_duplicates:
        print(f"Reached stopping condition: {max_duplicates} duplicate {ITEM_NAME}s seen in a row.")
        
    print(f"Finished. Total downloaded this session: {downloaded_this_session}")
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        try:
            run(playwright)
        except Exception:
            pass
        finally:
            sys.exit(0)

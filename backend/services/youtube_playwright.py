import os
import time
from playwright.sync_api import sync_playwright, TimeoutError

def upload_video_playwright(file_path: str, title: str, description: str, project_id: int = 1):
    user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "profiles", f"project_{project_id}")
    
    with sync_playwright() as p:
        # Launch persistent context to keep cookies/session
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False, # We show the browser so user can see the progress and bypass captcha if any
            channel="chrome", # Use real Chrome to bypass Google bot detection
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"],
            no_viewport=True
        )
        
        try:
            page = browser.pages[0] if browser.pages else browser.new_page()
            
            page.goto("https://studio.youtube.com/")
            
            # 1. Login check
            if "accounts.google.com" in page.url or "signin" in page.url or "v2/web/createchannel" in page.url:
                print("Ожидание входа в аккаунт...")
                try:
                    # Give user 5 minutes to login and arrive at studio
                    page.wait_for_url("https://studio.youtube.com/channel/**", timeout=300000)
                except TimeoutError:
                    raise Exception("Таймаут авторизации. Зайдите в аккаунт YouTube в открывшемся браузере и повторите загрузку.")
                    
            time.sleep(5)
            
            # Check if there are any promotional/welcome popups to close
            print("Закрытие приветственных окон...")
            try:
                for _ in range(3):
                    page.keyboard.press("Escape")
                    time.sleep(0.5)
                
                # Попытка нажать кнопки "Закрыть", "ОК" или "Далее" в всплывающих окнах
                for button_selector in [
                    "ytcp-button#close-button", 
                    "ytcp-button#acknowledge-button",
                    "ytcp-button#action-button",
                    "ytcp-button.got-it-button"
                ]:
                    try:
                        page.locator(button_selector).click(timeout=1000)
                    except:
                        pass
            except:
                pass
                
            time.sleep(1)

            # 2. Upload Flow
            try:
                # Самый простой путь - большая кнопка по центру "Добавить видео" (если канал новый)
                page.get_by_text("Добавить видео").first.click(timeout=5000)
            except:
                try:
                    # Кнопка "Создать" в правом верхнем углу
                    page.get_by_text("Создать", exact=True).click(timeout=5000)
                    time.sleep(1)
                    page.get_by_text("Загрузить видео").first.click(timeout=5000)
                except:
                    # Иконка стрелочки вверх
                    try:
                        page.locator("#upload-icon").click(timeout=5000)
                    except:
                        pass
            
            time.sleep(2)
            
            # 3. Set file
            page.set_input_files("input[type=file]", file_path)
            
            # Wait for upload modal
            page.wait_for_selector("#textbox", timeout=30000)
            time.sleep(3)
            
            # 4. Fill Details
            textboxes = page.locator("#textbox").all()
            if len(textboxes) >= 2:
                # Clear and fill Title
                textboxes[0].click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                textboxes[0].fill(title[:100])
                time.sleep(1)
                
                # Clear and fill Description
                textboxes[1].click()
                page.keyboard.press("Control+A")
                page.keyboard.press("Backspace")
                textboxes[1].fill(description[:5000])
                time.sleep(1)
                
            # Click "Not made for kids" radio
            try:
                page.locator("tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']").click(timeout=5000)
            except:
                pass
                
            time.sleep(1)
            
            # Next button until Visibility
            for _ in range(3):
                page.click("#next-button")
                time.sleep(1.5)
                
            # 5. Set Privacy (Private)
            try:
                page.locator("tp-yt-paper-radio-button[name='PRIVATE']").click(timeout=5000)
            except:
                pass
                
            time.sleep(1)
            
            # 6. Publish / Save
            page.click("#done-button")
            
            # Wait for upload to complete
            # We check if the dialog is closed or shows "Video uploaded"
            try:
                # The close button appears when it's done uploading or if it's processing
                page.wait_for_selector("ytcp-button#close-button", timeout=60000)
                page.click("ytcp-button#close-button")
            except:
                time.sleep(20) # Fallback wait
            
            time.sleep(5)
            
        except Exception as e:
            try:
                page.screenshot(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "debug_youtube_error.png"))
                print("Скриншот ошибки сохранен в debug_youtube_error.png")
            except:
                pass
            raise e
        finally:
            browser.close()
            
    return {"status": "ok", "id": "playwright_upload"}

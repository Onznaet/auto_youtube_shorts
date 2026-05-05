import os
from playwright.sync_api import sync_playwright

user_data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "youtube_session")

def main():
    print("Запускаю браузер для авторизации...")
    with sync_playwright() as p:
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=False,
            channel="chrome",
            args=[
                "--no-sandbox", 
                "--disable-setuid-sandbox", 
                "--start-maximized",
                "--disable-blink-features=AutomationControlled"
            ],
            ignore_default_args=["--enable-automation"],
            no_viewport=True
        )
        
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://studio.youtube.com/")
        
        print("\n" + "="*50)
        print("Браузер открыт! Пожалуйста, войдите в свой аккаунт YouTube.")
        print("Проходите все проверки безопасности (СМС, подтверждения и т.д.) не торопясь.")
        print("Как только вы успешно войдете и увидите панель Студии YouTube — просто ЗАКРЫТЬ браузер на крестик!")
        print("="*50 + "\n")
        
        # Ждем, пока пользователь сам не закроет окно (бесконечно)
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
            
        print("Браузер закрыт. Сессия успешно сохранена!")

if __name__ == "__main__":
    main()

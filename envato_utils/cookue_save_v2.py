import json
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

COOKIE_FILE = "envato_cookies.json"
LOGIN_URL = "https://elements.envato.com/ru/sign-in"

def save_cookies_after_login():
    # Настройки браузера
    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    # Запуск браузера
    driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)
    driver.get(LOGIN_URL)

    print("Откройте страницу, залогиньтесь и дождитесь перехода на https://elements.envato.com/ru/")
    while True:
        current_url = driver.current_url
        if current_url.startswith("https://elements.envato.com/ru/"):
            break
        time.sleep(2)

    cookies = driver.get_cookies()

    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        json.dump(cookies, f, indent=4, ensure_ascii=False)

    print(f"✅ Cookies сохранены в {COOKIE_FILE}")
    driver.quit()

if __name__ == "__main__":
    save_cookies_after_login()

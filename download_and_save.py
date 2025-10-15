import time
import sys
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException, ElementClickInterceptedException
)

# ======================= НАСТРОЙКИ =======================
RESULTS_FILE = Path("test_results.xlsx")
CHROMEDRIVER_PATH = None
HEADLESS = False
PASSWORD = "Aa123456"
BASE_DOWNLOAD_DIR = Path("downloads")
DELAY = 0.4

LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"

SHORT_WAIT = 6
MID_WAIT = 8
DL_WAIT = 35
# =========================================================


# ---------------- НАСТРОЙКА ДРАЙВЕРА ----------------
def start_driver(driver_path=None, headless=False):
    options = webdriver.ChromeOptions()
    prefs = {
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ru")
    driver = webdriver.Chrome(executable_path=driver_path, options=options) if driver_path else webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


def set_download_dir(driver, directory: Path):
    directory.mkdir(parents=True, exist_ok=True)
    dl = str(directory.resolve())
    try:
        driver.execute_cdp_cmd("Page.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl})
    except Exception:
        try:
            driver.execute_cdp_cmd("Browser.setDownloadBehavior", {"behavior": "allow", "downloadPath": dl})
        except Exception:
            pass


# ---------------- ВСПОМОГАТЕЛЬНЫЕ ----------------
def safe_click(driver, xpath, wait=SHORT_WAIT):
    try:
        el = WebDriverWait(driver, wait).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        return False


def login(driver, email, password):
    try:
        driver.get(LOGIN_URL)
        WebDriverWait(driver, MID_WAIT).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        driver.find_element(By.XPATH, "//input[@type='email']").send_keys(email)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(password)
        safe_click(driver, "//button[contains(., 'Войти')]", wait=SHORT_WAIT)
        WebDriverWait(driver, MID_WAIT).until(lambda d: DASHBOARD_URL in d.current_url)
        print(f"✅ {email} вошёл")
        return True
    except Exception as e:
        print(f"❌ Ошибка входа {email}: {e}")
        return False


def open_results_page(driver):
    """Открывает 'Мои тесты' -> 'Просмотреть результаты'."""
    try:
        safe_click(driver, "//button[contains(., 'Перейти к тестам')]", wait=MID_WAIT)
        safe_click(driver, "//button[contains(., 'Мои тесты')]", wait=MID_WAIT)

        res_btn = WebDriverWait(driver, MID_WAIT).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Просмотреть результаты')]"))
        )
        driver.execute_script("arguments[0].click();", res_btn)
        WebDriverWait(driver, MID_WAIT).until(lambda d: "test-results" in d.current_url)
        print("📄 Открыта страница результатов теста")
        return True
    except Exception as e:
        print(f"⚠️ Не удалось открыть результаты: {e}")
        return False


# ---------------- СКАЧИВАНИЕ ----------------
def _wait_new_pdf(save_dir: Path, before_set: set, timeout: int = DL_WAIT):
    """Ждём появление РОВНО одного нового pdf (без .crdownload)."""
    end = time.time() + timeout
    while time.time() < end:
        current = set(save_dir.glob("*.pdf"))
        diff = current - before_set
        if diff:
            # последний по времени
            candidate = max(diff, key=lambda p: p.stat().st_mtime)
            # убедимся, что загрузка завершена (нет .crdownload)
            if not candidate.with_suffix(candidate.suffix + ".crdownload").exists():
                return candidate
        time.sleep(0.4)
    return None


def click_get_and_download(driver, label_text: str, save_dir: Path, target_name: str):
    final_path = save_dir / target_name
    if final_path.exists() and final_path.stat().st_size > 0:
        print(f"✅ Уже есть: {final_path.name} — пропускаю")
        return

    before = set(save_dir.glob("*.pdf"))

    try:
        # 1️⃣ Находим контейнер-ячейку с нужным текстом
        container_xpath = f"//div[contains(@class,'MuiGrid-item')][.//p[contains(normalize-space(.), '{label_text}')]]"
        container = WebDriverWait(driver, MID_WAIT).until(
            EC.presence_of_element_located((By.XPATH, container_xpath))
        )

        # 2️⃣ Нажимаем 'Получить' если есть
        get_btn_xpath = ".//button[contains(normalize-space(.), 'Получить')]"
        dl_btn_xpath  = ".//button[contains(normalize-space(.), 'Скачать')]"

        get_btns = container.find_elements(By.XPATH, get_btn_xpath)
        if get_btns:
            btn_get = get_btns[0]
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_get)
            time.sleep(0.3)
            try:
                btn_get.click()
            except Exception:
                driver.execute_script("arguments[0].click();", btn_get)
            print(f"🟢 Нажал 'Получить' для: {label_text}")
        else:
            print(f"ℹ️ 'Получить' не найдена (возможно уже нажата) для: {label_text}")

        # 3️⃣ Ждём замену на 'Скачать'
        btn_dl = None
        for _ in range(40):  # ~20 сек
            try:
                container = driver.find_element(By.XPATH, container_xpath)
                btns = container.find_elements(By.XPATH, dl_btn_xpath)
                if btns:
                    btn_dl = btns[0]
                    if btn_dl.is_enabled():
                        break
            except Exception:
                pass
            time.sleep(0.5)

        if not btn_dl:
            print(f"⚠️ Не дождался кнопки 'Скачать' для: {label_text}")
            return

        # 4️⃣ Нажимаем 'Скачать'
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_dl)
        time.sleep(0.5)
        try:
            btn_dl.click()
        except Exception:
            driver.execute_script("arguments[0].click();", btn_dl)
        print(f"⬇️ Нажал 'Скачать' для: {label_text}")

        # 5️⃣ Ждём появление файла
        new_file = _wait_new_pdf(save_dir, before, timeout=DL_WAIT)
        if new_file:
            if final_path.exists() and final_path.stat().st_size == 0:
                final_path.unlink(missing_ok=True)
            new_file.rename(final_path)
            print(f"📄 Сохранён файл: {final_path.name}")
        else:
            print(f"⚠️ Не дождался загрузки PDF для: {label_text}")

    except Exception as e:
        print(f"🔥 Ошибка при скачивании {label_text}: {e}")





def download_certificates(driver, user_dir: Path) -> str:
    set_download_dir(driver, user_dir)
    try:
        WebDriverWait(driver, MID_WAIT).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'доступен')]"))
        )
        print("📜 Найдены файлы для скачивания")
    except TimeoutException:
        print("⚠️ Сертификаты не найдены")
        return "N/A"

    # ВАЖНО: сначала диплом, потом сертификат (фикс дублирования имён)
    click_get_and_download(driver, "Диплом доступен", user_dir, "Диплом.pdf")
    click_get_and_download(driver, "Сертификат доступен", user_dir, "Сертификат.pdf")

    # Процент результата (если есть)
    try:
        score_el = WebDriverWait(driver, SHORT_WAIT).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), '%')]"))
        )
        return score_el.text.strip()
    except Exception:
        return "N/A"


# ---------------- ВЫХОД ----------------
def logout(driver):
    """
    Быстрый и надёжный выход:
    1) всегда уходим на DASHBOARD_URL;
    2) пытаемся кликнуть 'Выйти из системы' коротким ожиданием;
    3) если не получилось — принудительно идём на LOGIN_URL (этого достаточно для нашего пайплайна).
    """
    try:
        driver.get(DASHBOARD_URL)
        # пробуем быстро кликнуть кнопку
        if safe_click(driver, "//button[contains(., 'Выйти из системы')]", wait=SHORT_WAIT):
            try:
                WebDriverWait(driver, SHORT_WAIT).until(lambda d: "login" in d.current_url)
                print("✅ Вышел из аккаунта (через Dashboard)\n")
                return
            except TimeoutException:
                pass
        # fallback — напрямую на логин
        driver.get(LOGIN_URL)
        WebDriverWait(driver, SHORT_WAIT).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        print("✅ Вышел из аккаунта (через Login)\n")
    except Exception:
        # последний шанс — просто перейти на логин
        try:
            driver.get(LOGIN_URL)
            print("✅ Вышел из аккаунта (форсированно через Login)\n")
        except Exception:
            print("⚠️ Не удалось выйти, продолжаю...\n")


# ---------------- MAIN ----------------
def main():
    if not RESULTS_FILE.exists():
        print("❌ Нет файла test_results.xlsx — сначала нужно запустить первый скрипт.")
        sys.exit(1)

    df = pd.read_excel(RESULTS_FILE, engine="openpyxl", dtype=str).fillna("")
    driver = start_driver(CHROMEDRIVER_PATH, headless=HEADLESS)

    new_results = []

    for _, row in df.iterrows():
        status = row.get("Status", "")
        email = row.get("Email", "")
        full_name = row.get("FullName", "")
        iin = row.get("IIN", "")

        if status not in ("DONE", "OK"):
            print(f"⏭️ Пропускаю {email} (статус {status})")
            new_results.append(row)
            continue

        lastname, firstname = full_name.split(" ", 1) if " " in full_name else (full_name, "")
        user_dir = BASE_DOWNLOAD_DIR / f"{lastname}_{firstname}_{iin}"

        print(f"\n==============================\n👤 {full_name} ({email})")

        if not login(driver, email, PASSWORD):
            print(f"❌ Не удалось войти: {email}")
            new_results.append(row)
            continue

        if open_results_page(driver):
            score = download_certificates(driver, user_dir)
            row["Message"] = "Сертификаты скачаны"
            row["Score"] = score
        else:
            row["Message"] = "Ошибка открытия результатов"

        new_results.append(row)

        # мгновенный выход
        logout(driver)
        time.sleep(DELAY)

    driver.quit()
    pd.DataFrame(new_results).to_excel(RESULTS_FILE, index=False)
    print("\n✅ Все сертификаты скачаны и сохранены в папке 'downloads'")


if __name__ == "__main__":
    main()

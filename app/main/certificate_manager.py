import time
import threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from django.db import transaction
from main.models import UserAccount

# ============ НАСТРОЙКИ ============
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOAD_DIR = BASE_DIR / "downloads"
PASSWORD = "Aa123456"
LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"
SHORT_WAIT = 6
MID_WAIT = 10
DL_WAIT = 40
MAX_THREADS = 3  # 👈 одновременно будет работать 3 браузера

process_thread = None
stop_requested = False
# ==================================


# ---------- НАСТРОЙКА ДРАЙВЕРА ----------
def start_driver(download_path: Path):
    options = webdriver.ChromeOptions()
    prefs = {
        "download.default_directory": str(download_path.resolve()),
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True,
    }
    options.add_experimental_option("prefs", prefs)

    # 👇 ВСЁ ЧТО НУЖНО ДЛЯ ТИХОГО РЕЖИМА
    options.add_argument("--headless=new")          # полностью скрытый браузер
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--window-size=1920,1080") # важно для headless
    options.add_argument("--log-level=3")           # убрать лишние логи
    options.add_argument("--lang=ru")
    options.add_argument("--hide-scrollbars")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-infobars")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-notifications")

    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)

    # 👇 Разрешаем скачивание PDF в headless
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": str(download_path.resolve())
    })

    return driver



def safe_click(driver, xpath, wait=SHORT_WAIT):
    try:
        el = WebDriverWait(driver, wait).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        return False


# ---------- ЛОГИН ----------
def login(driver, email):
    try:
        driver.get(LOGIN_URL)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        driver.find_element(By.XPATH, "//input[@type='email']").send_keys(email)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(PASSWORD)
        safe_click(driver, "//button[contains(., 'Войти')]", wait=SHORT_WAIT)
        WebDriverWait(driver, 15).until(lambda d: DASHBOARD_URL in d.current_url)
        print(f"✅ Вошёл: {email}")
        return True
    except Exception as e:
        print(f"❌ Ошибка входа {email}: {e}")
        return False


def open_results_page(driver):
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
        print(f"⚠️ Ошибка открытия результатов: {e}")
        return False


def _wait_new_pdf(save_dir: Path, before_set: set, timeout: int = DL_WAIT):
    end = time.time() + timeout
    while time.time() < end:
        current = set(save_dir.glob("*.pdf"))
        diff = current - before_set
        if diff:
            candidate = max(diff, key=lambda p: p.stat().st_mtime)
            # ждём окончания загрузки
            if not candidate.with_suffix(candidate.suffix + ".crdownload").exists():
                return candidate
        time.sleep(0.4)
    return None


def click_get_and_download(driver, label_text: str, save_dir: Path, target_name: str):
    final_path = save_dir / target_name
    before = set(save_dir.glob("*.pdf"))

    try:
        container_xpath = f"//div[contains(@class,'MuiGrid-item')][.//p[contains(normalize-space(.), '{label_text}')]]"
        container = WebDriverWait(driver, MID_WAIT).until(
            EC.presence_of_element_located((By.XPATH, container_xpath))
        )

        get_btn_xpath = ".//button[contains(normalize-space(.), 'Получить')]"
        dl_btn_xpath = ".//button[contains(normalize-space(.), 'Скачать')]"

        get_btns = container.find_elements(By.XPATH, get_btn_xpath)
        if get_btns:
            driver.execute_script("arguments[0].click();", get_btns[0])
            print(f"🟢 Нажал 'Получить' для: {label_text}")
        else:
            print(f"ℹ️ 'Получить' не найдена, возможно уже активирована.")

        btn_dl = None
        for _ in range(60):
            container = driver.find_element(By.XPATH, container_xpath)
            btns = container.find_elements(By.XPATH, dl_btn_xpath)
            if btns:
                btn_dl = btns[0]
                if btn_dl.is_enabled():
                    break
            time.sleep(0.5)

        if not btn_dl:
            print(f"⚠️ Не дождался кнопки 'Скачать' для: {label_text}")
            return False

        driver.execute_script("arguments[0].click();", btn_dl)
        print(f"⬇️ Нажал 'Скачать' для: {label_text}")

        new_file = _wait_new_pdf(save_dir, before, timeout=DL_WAIT)
        if new_file:
            new_file.rename(final_path)
            print(f"📄 Сохранён файл: {final_path.name}")
            return True
        else:
            print("⚠️ Не дождался загрузки PDF")
            return False

    except Exception as e:
        print(f"🔥 Ошибка при скачивании {label_text}: {e}")
        return False


def download_certificate(user):
    """Скачивает сертификат для одного пользователя (в отдельном потоке, в общую папку)"""
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    driver = start_driver(DOWNLOAD_DIR)

    try:
        if not login(driver, user.email):
            user.has_error = True
            user.message = "Ошибка входа"
            user.save()
            return

        if not open_results_page(driver):
            user.has_error = True
            user.message = "Ошибка открытия результатов"
            user.save()
            return

        WebDriverWait(driver, MID_WAIT).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'Сертификат доступен')]"))
        )
        filename = f"{user.iin}_{user.full_name}_Сертификат.pdf"
        success = click_get_and_download(driver, "Сертификат доступен", DOWNLOAD_DIR, filename)

        if success:
            user.is_downloaded = True
            user.message = "Сертификат скачан"
        else:
            user.has_error = True
            user.message = "Ошибка скачивания"
        user.save()

    except TimeoutException:
        user.has_error = True
        user.message = "Сертификат не найден"
        user.save()
        print(f"⚠️ {user.email} — сертификат не найден")

    except Exception as e:
        user.has_error = True
        user.message = f"Ошибка: {e}"
        user.save()
        print(f"❌ {user.email} — исключение: {e}")

    finally:
        driver.quit()



# ---------- ОСНОВНОЙ МНОГОПОТОЧНЫЙ ПРОЦЕСС ----------
def download_process_parallel():
    global stop_requested
    stop_requested = False

    users = list(UserAccount.objects.filter(is_tested=True, is_downloaded=False, has_error=False))
    if not users:
        print("⏳ Нет новых сертификатов для скачивания")
        return

    print(f"📥 Найдено {len(users)} пользователей для скачивания")
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(download_certificate, user): user for user in users}

        for future in as_completed(futures):
            if stop_requested:
                print("⏹ Процесс остановлен пользователем")
                break
            user = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"💥 Ошибка потока {user.email}: {e}")

    print("✅ Все загрузки завершены")


# ---------- УПРАВЛЕНИЕ ----------
def start_downloading():
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        print("⚠️ Процесс уже запущен")
        return False

    stop_requested = False
    process_thread = threading.Thread(target=download_process_parallel, daemon=True)
    process_thread.start()
    return True


def stop_downloading():
    global stop_requested
    stop_requested = True
    print("⏹ Остановлено вручную")
    return True


def get_status():
    total = UserAccount.objects.filter(is_tested=True).count()
    downloaded = UserAccount.objects.filter(is_downloaded=True).count()
    running = process_thread.is_alive() if process_thread else False
    return {
        "total": total,
        "downloaded": downloaded,
        "running": running,
    }

# main/certificate_manager.py
import time
import threading
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

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

process_thread = None
stop_requested = False
# ==================================


# ---------- НАСТРОЙКА ДРАЙВЕРА ----------
def start_driver():
    options = webdriver.ChromeOptions()
    prefs = {
        "download.prompt_for_download": False,
        "plugins.always_open_pdf_externally": True
    }
    options.add_experimental_option("prefs", prefs)
    options.add_argument("--lang=ru")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


def set_download_dir(driver):
    DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    driver.execute_cdp_cmd("Page.setDownloadBehavior", {
        "behavior": "allow",
        "downloadPath": str(DOWNLOAD_DIR.resolve())
    })


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


# ---------- ПЕРЕХОД К РЕЗУЛЬТАТАМ ----------
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


# ---------- ПОМОЩНИКИ ДЛЯ СКАЧИВАНИЯ ----------
def _wait_new_pdf(save_dir: Path, before_set: set, timeout: int = DL_WAIT):
    end = time.time() + timeout
    while time.time() < end:
        current = set(save_dir.glob("*.pdf"))
        diff = current - before_set
        if diff:
            candidate = max(diff, key=lambda p: p.stat().st_mtime)
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

        # Нажимаем "Получить"
        get_btns = container.find_elements(By.XPATH, get_btn_xpath)
        if get_btns:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", get_btns[0])
            driver.execute_script("arguments[0].click();", get_btns[0])
            print(f"🟢 Нажал 'Получить' для: {label_text}")
        else:
            print(f"ℹ️ 'Получить' не найдена, вероятно уже нажата.")

        # Ждём кнопку "Скачать"
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

        # Нажимаем "Скачать"
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", btn_dl)
        time.sleep(0.4)
        driver.execute_script("arguments[0].click();", btn_dl)
        print(f"⬇️ Нажал 'Скачать' для: {label_text}")

        # Ждём файл
        new_file = _wait_new_pdf(save_dir, before, timeout=DL_WAIT)
        if new_file:
            new_file.rename(final_path)
            print(f"📄 Сохранён файл: {final_path.name}")
            return True
        else:
            print(f"⚠️ Не дождался загрузки PDF")
            return False

    except Exception as e:
        print(f"🔥 Ошибка при скачивании {label_text}: {e}")
        return False


# ---------- СКАЧИВАНИЕ СЕРТИФИКАТОВ ----------
def download_certificate(driver, user):
    set_download_dir(driver)
    try:
        WebDriverWait(driver, MID_WAIT).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'Сертификат доступен')]"))
        )
        print("📜 Найден сертификат, начинаю загрузку...")
        filename = f"{user.iin}_{user.full_name}_Сертификат.pdf"
        success = click_get_and_download(driver, "Сертификат доступен", DOWNLOAD_DIR, filename)

        if success:
            user.is_downloaded = True
            user.message = "Сертификат скачан"
        else:
            user.has_error = True
            user.message = "Ошибка скачивания сертификата"
        user.save()
    except TimeoutException:
        user.has_error = True
        user.message = "Сертификат не найден"
        user.save()
        print("⚠️ Сертификат не найден")


# ---------- ВЫХОД ----------
def logout(driver):
    try:
        driver.get(DASHBOARD_URL)
        safe_click(driver, "//button[contains(., 'Выйти из системы')]", wait=SHORT_WAIT)
        time.sleep(1)
    except Exception:
        driver.get(LOGIN_URL)


# ---------- ОСНОВНОЙ ПРОЦЕСС ----------
def download_process():
    global stop_requested
    stop_requested = False

    processed = 0
    driver = None

    while not stop_requested:
        try:
            # перезапускаем браузер каждые 20 пользователей
            if not driver or processed % 20 == 0:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                driver = start_driver()
                print("♻️ Перезапущен браузер Selenium")

            users = UserAccount.objects.filter(
                is_tested=True, is_downloaded=False, has_error=False
            )

            if not users.exists():
                print("⏳ Новых сертификатов нет, жду 60 секунд...")
                time.sleep(60)
                continue

            total = users.count()
            print(f"📥 Найдено {total} пользователей для скачивания")

            for user in users:
                if stop_requested:
                    print("⏹ Остановлено пользователем")
                    break

                print(f"\n👤 {user.full_name} ({user.email})")

                try:
                    if not login(driver, user.email):
                        user.has_error = True
                        user.message = "Ошибка входа"
                        user.save()
                        continue

                    if open_results_page(driver):
                        download_certificate(driver, user)
                    else:
                        user.has_error = True
                        user.message = "Ошибка открытия результатов"
                        user.save()

                except Exception as e:
                    print(f"❌ Ошибка при скачивании для {user.email}: {e}")
                    user.has_error = True
                    user.message = f"Исключение: {e}"
                    user.save()

                finally:
                    logout(driver)
                    processed += 1
                    time.sleep(1)

            # пауза перед следующей проверкой
            print("🔁 Проверяю снова через 30 секунд...")
            time.sleep(30)

        except Exception as e:
            print(f"💥 Критическая ошибка: {e}. Перезапуск через 10 секунд.")
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            time.sleep(10)
            driver = start_driver()

    if driver:
        try:
            driver.quit()
        except Exception:
            pass
    print("✅ Процесс скачивания завершён")



# ---------- УПРАВЛЕНИЕ ----------
def start_downloading():
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        print("⚠️ Процесс уже запущен")
        return False

    stop_requested = False
    process_thread = threading.Thread(target=download_process, daemon=True)
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
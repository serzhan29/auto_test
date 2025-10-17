import time
import threading
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .models import UserAccount, AutomationLog


# ====================== НАСТРОЙКИ ======================
BASE = "https://amlacademy.kz"
REG_URL = BASE + "/finiq/registration"
ORG = "Предприниматель города Кентау"
PASSWORD = "Aa123456"
CATEGORY = "Взрослый, Студент"
DELAY = 0.6  # между пользователями
# =======================================================

process_thread = None
stop_requested = False


# -------------------- Selenium helpers --------------------
def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ru")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


def safe_find(driver, by, selector, timeout=4):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None


def select_second_last_option(driver, dropdown_div, wait=3):
    """Выбирает предпоследний регион"""
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_div)
        dropdown_div.click()
        time.sleep(0.4)
        options = WebDriverWait(driver, wait).until(
            EC.presence_of_all_elements_located((By.XPATH, "//li | //div[@role='option']"))
        )
        if len(options) >= 2:
            target = options[-2]
            driver.execute_script("arguments[0].click();", target)
            print(f"✅ Регион выбран: {target.text.strip()}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при выборе региона: {e}")
    return False


def select_category(driver, category_text="Взрослый, Студент"):
    """Выбирает категорию"""
    try:
        category_div = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.ID, "category"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", category_div)
        category_div.click()

        option = WebDriverWait(driver, 3).until(
            EC.element_to_be_clickable((By.XPATH, f"//li[contains(., '{category_text}')]"))
        )
        driver.execute_script("arguments[0].click();", option)
        print(f"✅ Категория выбрана: {category_text}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при выборе категории: {e}")
        return False


# -------------------- Регистрация --------------------
def register_one(driver, user):
    driver.get(REG_URL)
    time.sleep(1)

    try:
        fio = user.full_name.split()
        lastname = fio[0] if len(fio) > 0 else ""
        firstname = fio[1] if len(fio) > 1 else ""
        middlename = " ".join(fio[2:]) if len(fio) > 2 else ""

        driver.find_element(By.NAME, "lastname").send_keys(lastname)
        driver.find_element(By.NAME, "firstname").send_keys(firstname)
        driver.find_element(By.NAME, "middlename").send_keys(middlename)

        # --- уникальный телефон
        if not hasattr(user, "phone") or not user.phone:
            user.phone = "+7777777" + str(random.randint(100, 999))
            user.save()
        driver.find_element(By.NAME, "phone").send_keys(user.phone)
        driver.find_element(By.NAME, "organization").send_keys(ORG)
        driver.find_element(By.NAME, "email").send_keys(user.email)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.NAME, "confirmPassword").send_keys(PASSWORD)

        # --- выбор региона и категории
        region = safe_find(driver, By.ID, "region")
        if region:
            select_second_last_option(driver, region)
        if not select_category(driver, CATEGORY):
            user.status = "failed"
            user.has_error = True
            user.message = "Не удалось выбрать категорию"
            user.save()
            return

        # --- регистрация
        reg_btn = safe_find(driver, By.XPATH, "//button[contains(., 'Зарегистрироваться') or @type='submit']")
        if not reg_btn:
            user.status = "failed"
            user.has_error = True
            user.message = "Не найдена кнопка 'Зарегистрироваться'"
            user.save()
            return

        driver.execute_script("arguments[0].click();", reg_btn)
        print("➡️ Нажата кнопка 'Зарегистрироваться'")

        # --- подтверждение
        try:
            confirm_btn = WebDriverWait(driver, 3).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Подтвердить') or contains(., 'отправить')]"))
            )
            driver.execute_script("arguments[0].click();", confirm_btn)
            print("✅ Подтверждение отправлено")
        except TimeoutException:
            pass

        time.sleep(2)

        # --- проверка результата
        end_time = time.time() + 12
        redirected = False
        already_exists = False
        phone_exists = False
        registration_failed = False
        other_error = None

        while time.time() < end_time:
            current = driver.current_url

            if "/finiq/login" in current:
                redirected = True
                break

            if driver.find_elements(By.XPATH, "//p[contains(., 'Student with this email already exists')]"):
                already_exists = True
                break
            if driver.find_elements(By.XPATH, "//p[contains(., 'Student with this phone number already exists')]"):
                phone_exists = True
                break
            if driver.find_elements(By.XPATH, "//div[contains(., 'Registration failed')]"):
                registration_failed = True
                break

            errors = driver.find_elements(By.XPATH, "//p[contains(@class,'Mui-error')] | //div[contains(@class,'MuiAlert-message')]")
            if errors:
                other_error = errors[0].text.strip()
                break

            time.sleep(0.3)

        if redirected:
            user.status = "registered"
            user.is_registered = True
            user.has_error = False
            user.message = "✅ Регистрация успешна (редирект на /login)"
        elif already_exists or phone_exists:
            user.status = "registered"
            user.is_registered = True
            user.has_error = False
            user.message = "ℹ️ Пользователь уже зарегистрирован"
        elif registration_failed:
            user.status = "failed"
            user.has_error = True
            user.message = "❌ Registration failed (сервер не принял данные)"
        elif other_error:
            user.status = "failed"
            user.has_error = True
            user.message = f"Ошибка: {other_error}"
        else:
            user.status = "failed"
            user.has_error = True
            user.message = "⚠️ Не удалось завершить регистрацию (редиректа нет)"

        user.save()
        time.sleep(1.2)

    except Exception as e:
        user.status = "failed"
        user.is_registered = False
        user.has_error = True
        user.message = f"Исключение: {e}"
        user.save()
        time.sleep(1)


# -------------------- Основной процесс --------------------
def registration_process():
    global stop_requested
    stop_requested = False
    driver = None
    processed = 0

    while not stop_requested:
        try:
            if not driver or processed % 100 == 0:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                driver = start_driver()
                print("♻️ Перезапуск браузера Selenium")

            users = UserAccount.objects.exclude(status__in=["registered", "tested", "completed"])
            if not users.exists():
                print("⏳ Новых пользователей нет, жду 30 секунд...")
                time.sleep(30)
                continue

            for user in users:
                if stop_requested:
                    print("⏸ Регистрация остановлена пользователем")
                    break

                if user.status in ["registered", "tested", "completed"]:
                    continue

                print(f"👤 Регистрирую: {user.full_name} ({user.email})")
                register_one(driver, user)
                processed += 1
                time.sleep(DELAY)

        except Exception as e:
            print(f"💥 Ошибка процесса: {e}")
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            time.sleep(3)
            driver = start_driver()

    if driver:
        try:
            driver.quit()
        except Exception:
            pass
    print("✅ Процесс регистрации завершён")


def start_registration():
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        return False
    stop_requested = False
    process_thread = threading.Thread(target=registration_process, daemon=True)
    process_thread.start()
    return True


def stop_registration():
    global stop_requested
    stop_requested = True
    return True


def get_status():
    total = UserAccount.objects.count()
    reg = UserAccount.objects.filter(status="registered").count()
    fail = UserAccount.objects.filter(status="failed").count()
    pend = UserAccount.objects.filter(status="pending").count()
    return {
        "total": total,
        "registered": reg,
        "failed": fail,
        "pending": pend,
        "running": process_thread.is_alive() if process_thread else False,
    }

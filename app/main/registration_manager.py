import time
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .models import UserAccount, AutomationLog

# ====================== НАСТРОЙКИ ======================
BASE = "https://amlacademy.kz"
REG_URL = BASE + "/finiq/registration"
PHONE = "+77777777878"
ORG = "Предприниматель города Кентау"
PASSWORD = "Aa123456"
CATEGORY = "Взрослый, Студент"

CHROMEDRIVER_PATH = None
DELAY = 0.5
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
    driver.implicitly_wait(5)
    return driver


def safe_find(driver, by, selector, timeout=6):
    try:
        return WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((by, selector))
        )
    except TimeoutException:
        return None


def select_second_last_option(driver, dropdown_div, wait=6):
    """Выбирает предпоследний регион"""
    try:
        driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_div)
        dropdown_div.click()
        time.sleep(0.5)
        options = WebDriverWait(driver, wait).until(
            EC.presence_of_all_elements_located((By.XPATH, "//li | //div[@role='option']"))
        )
        if len(options) >= 2:
            target = options[-2]
            driver.execute_script("arguments[0].scrollIntoView(true);", target)
            driver.execute_script("arguments[0].click();", target)
            print(f"✅ Регион выбран: {target.text.strip()}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при выборе региона: {e}")
    return False


def select_category(driver, category_text="Взрослый, Студент"):
    try:
        category_div = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.ID, "category"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", category_div)
        category_div.click()

        option = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//li[@role='option' and contains(., '{category_text}')]"))
        )
        driver.execute_script("arguments[0].scrollIntoView(true);", option)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", option)

        print(f"✅ Категория выбрана: {category_text}")
        return True
    except Exception as e:
        print(f"❌ Ошибка при выборе категории: {e}")
        return False



# -------------------- Регистрация --------------------
def log_action(user, stage, success, message=""):
    """Создаёт запись в AutomationLog"""
    AutomationLog.objects.create(user=user, stage=stage, success=success, message=message)


def register_one(driver, user):
    driver.get(REG_URL)
    time.sleep(1)

    try:
        # --- 1) Заполнение формы
        fio = user.full_name.split()
        lastname = fio[0] if len(fio) > 0 else ""
        firstname = fio[1] if len(fio) > 1 else ""
        middlename = " ".join(fio[2:]) if len(fio) > 2 else ""

        driver.find_element(By.NAME, "lastname").send_keys(lastname)
        driver.find_element(By.NAME, "firstname").send_keys(firstname)
        driver.find_element(By.NAME, "middlename").send_keys(middlename)
        driver.find_element(By.NAME, "phone").send_keys(PHONE)
        driver.find_element(By.NAME, "organization").send_keys(ORG)
        driver.find_element(By.NAME, "email").send_keys(user.email)
        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.NAME, "confirmPassword").send_keys(PASSWORD)

        # --- 2) Регион
        region = safe_find(driver, By.ID, "region")
        if region:
            select_second_last_option(driver, region)

        # --- 3) Категория (ОБЯЗАТЕЛЬНО "Взрослый, Студент")
        if not select_category(driver, CATEGORY):
            user.status = "failed"
            user.has_error = True
            user.message = "Не удалось выбрать категорию"
            user.save()
            return

        # --- 4) Нажать "Зарегистрироваться"
        reg_btn = safe_find(driver, By.XPATH, "//button[contains(., 'Зарегистрироваться') or @type='submit']")
        if not reg_btn:
            user.status = "failed"
            user.has_error = True
            user.message = "Не найдена кнопка 'Зарегистрироваться'"
            user.save()
            return

        driver.execute_script("arguments[0].scrollIntoView(true);", reg_btn)
        time.sleep(0.2)
        driver.execute_script("arguments[0].click();", reg_btn)
        print("➡️ Нажата кнопка 'Зарегистрироваться'")

        # --- 5) Попробовать подтвердить модалку
        try:
            confirm_btn = WebDriverWait(driver, 6).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Подтвердить') or contains(., 'отправить')]"))
            )
            time.sleep(0.4)
            driver.execute_script("arguments[0].click();", confirm_btn)
            print("✅ Нажата кнопка 'Подтвердить и отправить'")
        except TimeoutException:
            # модалка могла не появиться — это ок, идём дальше и проверяем исходы
            pass

        # --- 6) Ждём один из исходов:
        #   A) Успех: редирект (уходит со /registration)
        #   B) Успех: сообщение "Student with this email already exists" (юзер уже есть)
        #   C) Иначе — ошибка
        end = time.time() + 10
        already_exists = False
        redirected = False

        while time.time() < end:
            # A) редирект
            if "registration" not in driver.current_url:
                redirected = True
                break

            # B) уже существует
            try:
                driver.find_element(
                    By.XPATH, "//p[contains(text(), 'Student with this email already exists')]"
                )
                already_exists = True
                break
            except Exception:
                pass

            time.sleep(0.3)

        # --- 7) Проставляем статусы корректно
        if redirected:
            user.status = "registered"
            user.is_registered = True
            user.has_error = False
            user.message = "Зарегистрирован (редирект)"
            user.save()
            return

        if already_exists:
            user.status = "registered"
            user.is_registered = True
            user.has_error = False       # <— ВАЖНО: это НЕ ошибка
            user.message = "Пользователь уже зарегистрирован"
            user.save()
            return

        # если сюда дошли — ни редиректа, ни сообщения
        user.status = "failed"
        user.is_registered = False
        user.has_error = True
        user.message = "Не удалось завершить регистрацию: ни редиректа, ни сообщения об уже существующем"
        user.save()

    except Exception as e:
        user.status = "failed"
        user.is_registered = False
        user.has_error = True
        user.message = f"Исключение: {e}"
        user.save()



# -------------------- Управление --------------------
def registration_process():
    """Основной поток регистрации"""
    global stop_requested
    stop_requested = False
    driver = start_driver()
    users = UserAccount.objects.exclude(status="registered")

    for user in users:
        if stop_requested:
            print("⏸ Регистрация остановлена пользователем")
            break

        print(f"👤 Регистрирую: {user.full_name} ({user.email})")
        register_one(driver, user)
        time.sleep(DELAY)

    driver.quit()
    print("✅ Процесс регистрации завершён")


def start_registration():
    """Запускает фоновый поток"""
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        return False  # уже запущено

    stop_requested = False
    process_thread = threading.Thread(target=registration_process, daemon=True)
    process_thread.start()
    return True


def stop_registration():
    """Останавливает процесс"""
    global stop_requested
    stop_requested = True
    return True


def get_status():
    """Возвращает текущую статистику"""
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

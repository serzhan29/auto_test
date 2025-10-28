import time
import threading
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from django.db import transaction
from .models import UserAccount

# ===================== НАСТРОЙКИ =====================
LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"
PASSWORD = "Aa123456"
DELAY = 0.6  # задержка между пользователями
MAX_THREADS = 5  # 👈 количество браузеров (одновременно тестирующих пользователей)

ANSWERS = {
    1: "a", 2: "c", 3: "b", 4: "a", 5: "c",
    6: "b", 7: "d", 8: "c", 9: "a", 10: "b",
    11: "c", 12: "a", 13: "a", 14: "b", 15: "a",
    16: "a", 17: "d", 18: "b", 19: "d", 20: "c"
}

process_thread = None
stop_requested = False
# =====================================================


# ------------------ НАСТРОЙКА БРАУЗЕРА ------------------
def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ru")
    options.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


# ------------------ ВСПОМОГАТЕЛЬНЫЕ ------------------
def safe_click(driver, xpath, wait=5):
    try:
        el = WebDriverWait(driver, wait).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", el)
        time.sleep(0.5)
        return True
    except Exception:
        return False


def get_question_number(driver):
    try:
        h = WebDriverWait(driver, 5).until(
            EC.presence_of_element_located((By.XPATH, "//h6[contains(., 'Вопрос')]"))
        )
        m = re.search(r"Вопрос\s+(\d+)", h.text)
        return int(m.group(1)) if m else 1
    except Exception:
        return 1


def normalize_to_first_question(driver):
    for _ in range(25):
        try:
            qn = get_question_number(driver)
            if qn <= 1:
                break
            if not safe_click(driver, "//button[contains(., 'Назад')]", wait=2):
                break
            time.sleep(0.3)
        except Exception:
            break


# ------------------ ОСНОВНЫЕ ПРОЦЕССЫ ------------------
def login(driver, email, password):
    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        driver.find_element(By.XPATH, "//input[@type='email']").send_keys(email)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(password)
        safe_click(driver, "//button[contains(., 'Войти')]", wait=6)
        WebDriverWait(driver, 10).until(lambda d: DASHBOARD_URL in d.current_url)
        print(f"✅ Вход выполнен: {email}")
        return True
    except Exception:
        print(f"❌ Ошибка входа: {email}")
        return False


def open_tests_page(driver):
    try:
        btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Перейти к тестам')]"))
        )
        driver.execute_script("arguments[0].click();", btn)
        time.sleep(1.2)
        return True
    except Exception:
        return False


def check_test_status(driver):
    try:
        open_tests_page(driver)
        time.sleep(1)
        my_tab = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Мои тесты')]"))
        )
        driver.execute_script("arguments[0].click();", my_tab)
        time.sleep(0.8)

        if driver.find_elements(By.XPATH, "//button[contains(., 'Просмотреть результаты')]"):
            return "done"

        available_tab = driver.find_element(By.XPATH, "//button[contains(., 'Доступные тесты')]")
        driver.execute_script("arguments[0].click();", available_tab)
        time.sleep(1)

        if driver.find_elements(By.XPATH, "//div[contains(., 'Failed to start exam session')]"):
            print("⚠️ Ошибка запуска теста — жду 3 сек и пробую заново...")
            time.sleep(3)
            driver.refresh()
            time.sleep(2)
            return check_test_status(driver)

        start_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Начать тест')]")
        if start_btns:
            driver.execute_script("arguments[0].click();", start_btns[0])
            time.sleep(2)
            return "available"

        return "none"
    except Exception:
        return "none"


def answer_questions(driver):
    normalize_to_first_question(driver)
    for i in range(1, 21):
        try:
            q_num = get_question_number(driver)
            letter = ANSWERS.get(q_num, "a")
            opts = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "label.MuiFormControlLabel-root p"))
            )
            for opt in opts:
                if opt.text.strip().lower().startswith(letter):
                    driver.execute_script("arguments[0].click();", opt.find_element(By.XPATH, "./ancestor::label"))
                    break
            if q_num < 20:
                safe_click(driver, "//button[contains(., 'Далее')]", wait=3)
            time.sleep(0.5)
        except Exception:
            pass


def finish_test(driver):
    try:
        safe_click(driver, "//button[contains(text(), 'Завершить')]", wait=10)
        time.sleep(1)
        confirm = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//div[contains(@role, 'dialog')]//button[contains(., 'Завершить')]"))
        )
        driver.execute_script("arguments[0].click();", confirm)
        time.sleep(2)
        el = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(@class,'MuiTypography-h2')]"))
        )
        score_text = el.text.strip()
        match = re.search(r"(\d+)%", score_text)
        score = match.group(1) + "%" if match else score_text
        print(f"✅ Тест завершён: {score}")
        return score, True
    except Exception as e:
        print(f"❌ Ошибка при завершении теста: {e}")
        return "N/A", False


def logout(driver):
    try:
        driver.get(DASHBOARD_URL)
        time.sleep(0.8)
        btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Выйти из системы')]"))
        )
        driver.execute_script("arguments[0].click();", btn)
        WebDriverWait(driver, 6).until(lambda d: "login" in d.current_url)
        print("🚪 Вышел из аккаунта")
    except Exception:
        driver.get(LOGIN_URL)
        print("🚪 Принудительный выход")


# ------------------ ОБРАБОТКА ОДНОГО ------------------
def process_user(user):
    """Обрабатывает одного пользователя в отдельном потоке"""
    driver = start_driver()
    try:
        print(f"👤 {user.email} — начинаю тест")
        with transaction.atomic():
            fresh_user = UserAccount.objects.select_for_update().get(pk=user.pk)
            if fresh_user.status not in ["registered"]:
                print(f"⏭ Пропуск {user.email}, статус уже изменился")
                return
            fresh_user.status = "testing"
            fresh_user.save()

        if not login(driver, user.email, PASSWORD):
            user.status = "failed"
            user.has_error = True
            user.message = "Ошибка входа"
            user.save()
            return

        state = check_test_status(driver)

        if state == "done":
            user.status = "tested"
            user.is_tested = True
            user.message = "✅ Уже сдан"
        elif state == "available":
            answer_questions(driver)
            score, ok = finish_test(driver)
            if ok:
                user.status = "tested"
                user.is_tested = True
                user.score = score
                user.message = f"✅ Тест сдан ({score})"
            else:
                user.status = "failed"
                user.has_error = True
                user.message = "Ошибка завершения теста"
        else:
            user.status = "failed"
            user.has_error = True
            user.message = "❌ Тест не найден или не доступен"

        user.save()

    except Exception as e:
        print(f"❌ Ошибка у {user.email}: {e}")
        user.status = "failed"
        user.has_error = True
        user.message = f"Ошибка: {e}"
        user.save()
    finally:
        logout(driver)
        driver.quit()
        time.sleep(DELAY)


# ------------------ МНОГОПОТОЧНЫЙ ПРОЦЕСС ------------------
def test_process_parallel():
    global stop_requested
    stop_requested = False
    users = list(UserAccount.objects.filter(status="registered"))
    print(f"👥 Найдено {len(users)} пользователей для теста")

    with ThreadPoolExecutor(max_workers=MAX_THREADS) as executor:
        futures = {executor.submit(process_user, user): user for user in users}

        for future in as_completed(futures):
            if stop_requested:
                print("⏸ Остановка тестирования пользователем")
                break
            user = futures[future]
            try:
                future.result()
            except Exception as e:
                print(f"💥 Ошибка в потоке {user.email}: {e}")

    print("✅ Все потоки завершили работу")


# ------------------ УПРАВЛЕНИЕ ------------------
def start_testing():
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        return False
    stop_requested = False
    process_thread = threading.Thread(target=test_process_parallel, daemon=True)
    process_thread.start()
    return True


def stop_testing():
    global stop_requested
    stop_requested = True
    return True


def get_status():
    total = UserAccount.objects.count()
    tested = UserAccount.objects.filter(status="tested").count()
    failed = UserAccount.objects.filter(status="failed").count()
    registered = UserAccount.objects.filter(status="registered").count()
    return {
        "total": total,
        "tested": tested,
        "failed": failed,
        "registered": registered,
        "running": process_thread.is_alive() if process_thread else False,
    }

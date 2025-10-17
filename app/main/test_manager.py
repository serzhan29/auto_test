import time
import threading
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from .models import UserAccount

# ===================== НАСТРОЙКИ =====================
LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"
PASSWORD = "Aa123456"
DELAY = 0.6  # задержка между пользователями

ANSWERS = {
    1: "a", 2: "c", 3: "b", 4: "a", 5: "c",
    6: "b", 7: "d", 8: "c", 9: "a", 10: "b",
    11: "c", 12: "a", 13: "a", 14: "b", 15: "a",
    16: "a", 17: "d", 18: "b", 19: "d", 20: "c"
}

process_thread = None
stop_requested = False
# =====================================================


def start_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--lang=ru")
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


# ----------------- ВСПОМОГАТЕЛЬНЫЕ -------------------
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
    """Переходит к первому вопросу"""
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
# -----------------------------------------------------


# ----------------- ОСНОВНЫЕ ПРОЦЕССЫ -----------------
def login(driver, email, password):
    """Авторизация"""
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
    """Открывает раздел тестов"""
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
    """Проверяет, доступен ли тест, и возвращает состояние"""
    try:
        open_tests_page(driver)
        time.sleep(1)

        # "Мои тесты"
        my_tab = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Мои тесты')]"))
        )
        driver.execute_script("arguments[0].click();", my_tab)
        time.sleep(0.8)

        if driver.find_elements(By.XPATH, "//button[contains(., 'Просмотреть результаты')]"):
            return "done"

        # "Доступные тесты"
        available_tab = driver.find_element(By.XPATH, "//button[contains(., 'Доступные тесты')]")
        driver.execute_script("arguments[0].click();", available_tab)
        time.sleep(1)

        # Проверяем "Failed to start exam session"
        if driver.find_elements(By.XPATH, "//div[contains(., 'Failed to start exam session')]"):
            print("⚠️ Ошибка: Failed to start exam session — сервер не запустил тест. Жду 3 сек и пробую заново...")
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
    """Отвечает на все вопросы"""
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
    """Завершает тест и возвращает результат"""
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

        print(f"✅ Тест завершён, результат: {score}")
        return score, True
    except Exception as e:
        print(f"❌ Ошибка при завершении теста: {e}")
        return "N/A", False


def logout(driver):
    """Выходит из аккаунта"""
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
        try:
            driver.get(LOGIN_URL)
            print("🚪 Вышел принудительно (через /login)")
        except Exception:
            pass


# ----------------- ОСНОВНОЙ ПОТОК -----------------
def test_process():
    global stop_requested
    stop_requested = False

    users = UserAccount.objects.filter(status="registered")
    driver = None
    processed = 0

    while True:
        try:
            if not driver or processed % 20 == 0:
                if driver:
                    try:
                        driver.quit()
                    except Exception:
                        pass
                driver = start_driver()
                print("♻️ Перезапуск браузера Selenium")

            for user in users:
                if stop_requested:
                    print("⏸ Тестирование остановлено пользователем")
                    break

                if user.status in ["tested", "completed"]:
                    continue

                print(f"👤 {user.email} — прохожу тест")
                user.status = "testing"
                user.save()

                try:
                    if not login(driver, user.email, PASSWORD):
                        user.status = "failed"
                        user.has_error = True
                        user.message = "Ошибка входа"
                        user.save()
                        continue

                    state = check_test_status(driver)

                    if state == "done":
                        user.status = "tested"
                        user.is_tested = True
                        user.message = "✅ Уже сдан"
                        user.save()

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
                        user.save()

                    else:
                        user.status = "failed"
                        user.has_error = True
                        user.message = "❌ Тест не найден или не доступен"
                        user.save()

                except Exception as e:
                    print(f"❌ Ошибка на пользователе {user.email}: {e}")
                    user.status = "failed"
                    user.has_error = True
                    user.message = f"Исключение: {e}"
                    user.save()

                finally:
                    logout(driver)
                    time.sleep(DELAY)
                    processed += 1

            users = UserAccount.objects.filter(status="registered")

            if stop_requested:
                break

        except Exception as e:
            print(f"💥 Критическая ошибка, перезапуск процесса: {e}")
            try:
                if driver:
                    driver.quit()
            except Exception:
                pass
            time.sleep(3)
            driver = start_driver()
            continue

    if driver:
        driver.quit()
    print("✅ Процесс тестирования завершён")


def start_testing():
    global process_thread, stop_requested
    if process_thread and process_thread.is_alive():
        return False
    stop_requested = False
    process_thread = threading.Thread(target=test_process, daemon=True)
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

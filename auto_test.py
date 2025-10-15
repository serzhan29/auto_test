import time
import sys
import re
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ======================= НАСТРОЙКИ =======================
EXCEL_FILE = r"D:\PyCharmProjects\auto_test\1-200-auto-test.xlsx"
CHROMEDRIVER_PATH = None
HEADLESS = False
PASSWORD = "Aa123456"
DELAY = 0.4
RESULTS_FILE = Path("test_results.xlsx")

LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"

# Ответы для всех 20 вопросов
ANSWERS = {
    1: "a", 2: "c", 3: "b", 4: "a", 5: "c",
    6: "b", 7: "d", 8: "c", 9: "a", 10: "b",
    11: "c", 12: "a", 13: "a", 14: "b", 15: "a",
    16: "a", 17: "d", 18: "b", 19: "d", 20: "c"
}
# =========================================================


# ---------- НАСТРОЙКА БРАУЗЕРА ----------
def start_driver(driver_path=None, headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ru")
    driver = webdriver.Chrome(executable_path=driver_path, options=options) if driver_path else webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    return driver


# ---------- ВСПОМОГАТЕЛЬНЫЕ ----------
def safe_click(driver, xpath, wait=5):
    try:
        el = WebDriverWait(driver, wait).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        return False


def get_question_number(driver) -> int:
    try:
        h = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h6[contains(., 'Вопрос')]"))
        )
        m = re.search(r"Вопрос\s+(\d+)", h.text)
        return int(m.group(1)) if m else 1
    except Exception:
        return 1


def normalize_to_first_question(driver):
    """Принудительно возвращается на 1 вопрос"""
    try:
        for _ in range(25):
            qn = get_question_number(driver)
            if qn <= 1:
                break
            if not (safe_click(driver, "//button[contains(., 'Назад')]", wait=2) or
                    safe_click(driver, "//button[contains(., 'Предыдущ')]", wait=2)):
                break
            time.sleep(0.4)
    except Exception:
        pass


# ---------- ОСНОВНОЙ ПРОЦЕСС ----------
def login(driver, email, password):
    driver.get(LOGIN_URL)
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
        driver.find_element(By.XPATH, "//input[@type='email']").send_keys(email)
        driver.find_element(By.XPATH, "//input[@type='password']").send_keys(password)
        safe_click(driver, "//button[contains(., 'Войти')]", wait=6)
        WebDriverWait(driver, 10).until(lambda d: DASHBOARD_URL in d.current_url)
        print(f"✅ {email} вошёл")
        return True
    except Exception as e:
        print(f"❌ Ошибка входа {email}: {e}")
        return False


def open_tests_page(driver):
    try:
        btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Перейти к тестам')]"))
        )
        driver.execute_script("arguments[0].click();", btn)
        print("✅ Перешёл к разделу 'Тесты'")
        time.sleep(0.8)
        return True
    except Exception as e:
        print(f"⚠️ Не удалось открыть раздел 'Тесты': {e}")
        return False


def check_test_status(driver):
    """Возвращает:
       done — тест уже сдан
       available — тест доступен для прохождения
       none — ничего не найдено
    """
    try:
        open_tests_page(driver)

        # Проверяем "Мои тесты"
        my_tests_tab = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Мои тесты')]"))
        )
        driver.execute_script("arguments[0].click();", my_tests_tab)
        time.sleep(0.8)

        res_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Просмотреть результаты')]")
        if res_btns:
            print("📊 Найден завершённый тест")
            return "done"

        # Проверяем "Доступные тесты"
        available_tab = driver.find_element(By.XPATH, "//button[contains(., 'Доступные тесты')]")
        driver.execute_script("arguments[0].click();", available_tab)
        time.sleep(0.5)
        start_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Начать тест')]")
        if start_btns:
            print("🟢 Найден тест для прохождения")
            driver.execute_script("arguments[0].click();", start_btns[0])
            return "available"

        return "none"
    except Exception as e:
        print(f"❌ Ошибка при проверке тестов: {e}")
        return "none"


def answer_questions(driver):
    print("🧠 Начинаю отвечать на вопросы...")
    normalize_to_first_question(driver)

    for i in range(1, 21):
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//h6[contains(., 'Вопрос')]"))
            )
            q_num = get_question_number(driver)
            letter = ANSWERS.get(q_num, "a")

            opts = WebDriverWait(driver, 5).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "label.MuiFormControlLabel-root p"))
            )

            clicked = False
            for opt in opts:
                if opt.text.strip().lower().startswith(letter):
                    driver.execute_script(
                        "arguments[0].click();", opt.find_element(By.XPATH, "./ancestor::label")
                    )
                    clicked = True
                    break

            if not clicked:
                print(f"⚠️ Не найден вариант {letter} для вопроса {q_num}")

            if q_num < 20:
                safe_click(driver, "//button[contains(., 'Далее')]", wait=3)
                try:
                    cancel_btn = WebDriverWait(driver, 1.5).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Отмена')]"))
                    )
                    driver.execute_script("arguments[0].click();", cancel_btn)
                except TimeoutException:
                    pass
            else:
                print("🎯 Все 20 вопросов пройдены!")
        except Exception as e:
            print(f"⚠️ Ошибка на вопросе {i}: {e}")
        time.sleep(0.4)


def finish_test(driver):
    print("🧩 Завершаю тест...")
    try:
        # Нажимаем кнопку "Завершить тест"
        safe_click(driver, "//button[contains(text(), 'Завершить тест') or contains(text(), 'Завершить')]", wait=8)
        time.sleep(1)

        # Подтверждаем завершение
        confirm_xpath = "//div[contains(@role, 'dialog')]//button[contains(., 'Завершить')]"
        confirm_btn = WebDriverWait(driver, 8).until(EC.element_to_be_clickable((By.XPATH, confirm_xpath)))
        driver.execute_script("arguments[0].click();", confirm_btn)
        print("✅ Подтверждение завершения нажато")

        # Ждём появления процента (например "95%")
        el = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), '%')]"))
        )
        score = el.text.strip()
        print(f"📊 Результат теста: {score}")

        # ⚡ Сразу переходим на Dashboard для выхода
        driver.get("https://amlacademy.kz/finiq/dashboard")
        time.sleep(0.7)

        return score, True  # test завершён, можно выходить

    except Exception as e:
        print(f"⚠️ Ошибка при завершении теста: {e}")
        try:
            driver.get("https://amlacademy.kz/finiq/dashboard")
        except Exception:
            pass
        return "N/A", False



def logout(driver):
    """Надёжный выход сразу через Dashboard"""
    try:
        # Переходим на главную панель
        driver.get("https://amlacademy.kz/finiq/dashboard")
        print("➡️ Перешёл на Dashboard для выхода")

        # Ищем кнопку "Выйти из системы"
        logout_btn = WebDriverWait(driver, 8).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Выйти из системы')]"))
        )

        # Нажимаем по кнопке
        driver.execute_script("arguments[0].click();", logout_btn)
        print("🚪 Нажата кнопка 'Выйти из системы'")

        # Проверяем, что перешёл на страницу логина
        WebDriverWait(driver, 6).until(lambda d: "login" in d.current_url)
        print("✅ Успешно вышел из аккаунта\n")

    except TimeoutException:
        print("⚠️ Не удалось найти кнопку выхода, переход напрямую на login")
        driver.get("https://amlacademy.kz/finiq/login")

    except Exception as e:
        print(f"⚠️ Ошибка при выходе: {e}")
        driver.get("https://amlacademy.kz/finiq/login")




# ---------- MAIN ----------
def main():
    excel_path = Path(EXCEL_FILE)
    if not excel_path.exists():
        print("❌ Excel файл не найден")
        sys.exit(1)

    df = pd.read_excel(excel_path, engine="openpyxl", dtype=str).fillna("")
    completed_emails = set()
    results = []

    if RESULTS_FILE.exists():
        prev = pd.read_excel(RESULTS_FILE, engine="openpyxl", dtype=str).fillna("")
        results = prev.values.tolist()

        # ⚙️ Пропускаем только тех, у кого реально сдан тест
        completed_emails = set(
            prev.loc[prev["Status"].isin(["DONE", "OK"]), "Email"].tolist()
        )

        print(f"📁 Найден отчёт, пропущу {len(completed_emails)} завершённых аккаунтов")

    driver = start_driver(CHROMEDRIVER_PATH, headless=HEADLESS)

    for _, row in df.iterrows():
        email = str(row.get("Email", "")).strip()
        iin = str(row.get("IIN", "")).strip()
        lastname = str(row.get("Lastname", "")).strip()
        firstname = str(row.get("Firstname", "")).strip()
        full_name = f"{lastname} {firstname}"

        if not email or email in completed_emails:
            print(f"⏭️ Пропускаю {email}")
            continue

        print(f"\n==============================\n👤 {full_name} ({email})")

        # 🔁 до 3 попыток войти
        logged_in = False
        for attempt in range(3):
            if login(driver, email, PASSWORD):
                logged_in = True
                break
            else:
                print(f"🔁 Повторная попытка входа ({attempt + 1}/3)")
                time.sleep(2)

        if not logged_in:
            print(f"❌ Не удалось войти в {email} после 3 попыток — пропускаю.")
            row_data = [iin, email, full_name, "FAILED", "N/A", "Ошибка входа"]
            results.append(row_data)
            pd.DataFrame(results, columns=["IIN", "Email", "FullName", "Status", "Score", "Message"]).to_excel(RESULTS_FILE, index=False)
            continue

        # Проверяем тест
        status = check_test_status(driver)
        if status == "done":
            row_data = [iin, email, full_name, "DONE", "N/A", "Уже сдан"]

        elif status == "available":
            answer_questions(driver)
            score, finished = finish_test(driver)

            # Проверяем, действительно ли тест завершился
            if finished and score != "N/A":
                row_data = [iin, email, full_name, "OK", score, "Тест сдан"]
            else:
                row_data = [iin, email, full_name, "PARTIAL", score, "Ошибка при завершении теста"]

        else:
            row_data = [iin, email, full_name, "NONE", "N/A", "Тест не найден"]

        results.append(row_data)
        pd.DataFrame(results, columns=["IIN", "Email", "FullName", "Status", "Score", "Message"]).to_excel(RESULTS_FILE, index=False)

        # 🚪 выходим из аккаунта
        logout(driver)
        time.sleep(DELAY)

    driver.quit()
    print("\n✅ Все результаты сохранены в test_results.xlsx")



if __name__ == "__main__":
    main()

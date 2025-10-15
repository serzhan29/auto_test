# multi_take_tests.py
import time
import sys
import re
from pathlib import Path
import pandas as pd
import concurrent.futures
from typing import Dict, Any, List, Tuple

# Selenium imports (each worker will import these too)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

# ======================= НАСТРОЙКИ =======================
EXCEL_FILE = r"D:\PyCharmProjects\auto_test\1-200-auto-test.xlsx"
CHROMEDRIVER_PATH = None  # путь к chromedriver, или None если в PATH
HEADLESS = True           # рекомендую True при параллельных запусках
MAX_WORKERS = 3           # одновременно выполняется N тестов
PASSWORD = "Aa123456"
DELAY_BETWEEN_ACCOUNTS = 0.4
RESULTS_FILE = Path("test_results.xlsx")

LOGIN_URL = "https://amlacademy.kz/finiq/login"
DASHBOARD_URL = "https://amlacademy.kz/finiq/dashboard"

# ответы на вопросы (как у тебя)
ANSWERS = {
    1: "a", 2: "c", 3: "b", 4: "a", 5: "c",
    6: "b", 7: "d", 8: "c", 9: "a", 10: "b",
    11: "c", 12: "a", 13: "a", 14: "b", 15: "a",
    16: "a", 17: "d", 18: "b", 19: "d", 20: "c"
}

# таймауты
IMPLICIT_WAIT = 3
SHORT_WAIT = 5
MID_WAIT = 8
DL_WAIT = 30

# =========================================================


# --------- Вспомогательные функции (в воркере) ----------
def start_driver_local(driver_path=None, headless=True):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1280,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ru")
    # отключаем автоматический prompt загрузок, если понадобится в будущем
    prefs = {"download.prompt_for_download": False}
    options.add_experimental_option("prefs", prefs)
    if driver_path:
        driver = webdriver.Chrome(executable_path=driver_path, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(IMPLICIT_WAIT)
    return driver


def safe_click_local(driver, xpath, wait=SHORT_WAIT):
    try:
        el = WebDriverWait(driver, wait).until(EC.element_to_be_clickable((By.XPATH, xpath)))
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", el)
        driver.execute_script("arguments[0].click();", el)
        return True
    except Exception:
        return False


def get_question_number_local(driver) -> int:
    try:
        h = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//h6[contains(., 'Вопрос')]"))
        )
        m = re.search(r"Вопрос\s+(\d+)", h.text)
        return int(m.group(1)) if m else 1
    except Exception:
        return 1


def normalize_to_first_question_local(driver):
    try:
        for _ in range(25):
            qn = get_question_number_local(driver)
            if qn <= 1:
                break
            if not (safe_click_local(driver, "//button[contains(., 'Назад')]", wait=2) or
                    safe_click_local(driver, "//button[contains(., 'Предыдущ')]", wait=2)):
                break
            time.sleep(0.3)
    except Exception:
        pass


# --------- Процесс сдачи теста для одного аккаунта (в воркере) ----------
def worker_take_test(account: Dict[str, str]) -> Dict[str, Any]:
    """
    account: {"IIN":..., "Email":..., "FullName":...}
    Возвращает dict с полями: IIN, Email, FullName, Status, Score, Message
    """
    email = account.get("Email", "")
    iin = account.get("IIN", "")
    name = account.get("FullName", "")

    result = {"IIN": iin, "Email": email, "FullName": name, "Status": "FAILED", "Score": "N/A", "Message": ""}

    driver = None
    try:
        driver = start_driver_local(CHROMEDRIVER_PATH, headless=HEADLESS)

        # ---- login ----
        driver.get(LOGIN_URL)
        try:
            WebDriverWait(driver, MID_WAIT).until(EC.presence_of_element_located((By.XPATH, "//input[@type='email']")))
            driver.find_element(By.XPATH, "//input[@type='email']").send_keys(email)
            driver.find_element(By.XPATH, "//input[@type='password']").send_keys(PASSWORD)
            safe_click_local(driver, "//button[contains(., 'Войти')]", wait=6)
            WebDriverWait(driver, MID_WAIT).until(lambda d: DASHBOARD_URL in d.current_url)
        except Exception as e:
            result["Message"] = f"Login failed: {e}"
            return result

        # ---- open tests page and decide what to do ----
        try:
            # Перейти к тестам
            if not safe_click_local(driver, "//button[contains(., 'Перейти к тестам')]", wait=6):
                # возможно уже на странице - try dashboard button
                pass
            time.sleep(0.5)
        except Exception:
            pass

        # Открываем "Мои тесты" сначала, проверяем, есть ли завершённый
        try:
            my_btn = WebDriverWait(driver, MID_WAIT).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Мои тесты')]")))
            driver.execute_script("arguments[0].click();", my_btn)
            time.sleep(0.6)
            res_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Просмотреть результаты')]")
            if res_btns:
                result["Status"] = "DONE"
                result["Message"] = "Already done"
                return result
        except Exception:
            # ignore, попробуем найти доступные
            pass

        # Открываем "Доступные тесты" и стартуем, если есть
        try:
            avail_btn = driver.find_element(By.XPATH, "//button[contains(., 'Доступные тесты')]")
            driver.execute_script("arguments[0].click();", avail_btn)
            time.sleep(0.5)
            start_btns = driver.find_elements(By.XPATH, "//button[contains(., 'Начать тест') or contains(., 'Пройти тест')]")
            if not start_btns:
                result["Status"] = "NONE"
                result["Message"] = "No available tests"
                return result
            # кликаем первый доступный
            driver.execute_script("arguments[0].click();", start_btns[0])
        except Exception:
            result["Status"] = "NONE"
            result["Message"] = "No available tests (exception)"
            return result

        # ---- отвечаем на вопросы ----
        try:
            normalize_to_first_question_local(driver)
            for _ in range(1, 21):
                # ждём вопрос
                WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.XPATH, "//h6[contains(., 'Вопрос')]")))
                qn = get_question_number_local(driver)
                # выберем букву
                letter = ANSWERS.get(qn, "a").lower()

                # Найдём варианты — адаптивный селектор
                opts = driver.find_elements(By.CSS_SELECTOR, "label.MuiFormControlLabel-root")
                clicked = False
                for label in opts:
                    try:
                        # текст внутри label может содержать "a) текст" или "A. текст" или просто "текст"
                        txt = label.text.strip().lower()
                        if txt.startswith(letter) or txt.startswith(letter + ")") or txt.startswith(letter + "."):
                            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", label)
                            driver.execute_script("arguments[0].click();", label)
                            clicked = True
                            break
                    except Exception:
                        continue

                if not clicked:
                    # fallback: кликаем первый вариант
                    if opts:
                        try:
                            driver.execute_script("arguments[0].click();", opts[0])
                        except Exception:
                            pass

                # Нажать Далее, если не последний
                try:
                    nxt = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Далее')]")))
                    driver.execute_script("arguments[0].click();", nxt)
                except TimeoutException:
                    # возможно на последнем или кнопка называется иначе
                    pass

                time.sleep(0.35)
        except Exception as e:
            result["Message"] = f"Answering failed: {e}"
            # попытаемся продолжить к завершению
        # ---- завершаем тест ----
        try:
            # Нажать Завершить тест
            try:
                finish_btn_clicked = safe_click_local(driver, "//button[contains(text(), 'Завершить тест') or contains(text(), 'Завершить')]", wait=6)
            except Exception:
                finish_btn_clicked = False

            # Подтвердить
            try:
                confirm_btn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//div[contains(@role, 'dialog')]//button[contains(., 'Завершить') or contains(., 'Подтвердить')]"))
                )
                driver.execute_script("arguments[0].click();", confirm_btn)
            except Exception:
                # иногда прямой click в диалоге не нужен/нет диалога
                pass

            # ждём процент результата
            try:
                el = WebDriverWait(driver, 12).until(EC.presence_of_element_located((By.XPATH, "//h2[contains(text(), '%')]")))
                score = el.text.strip()
            except Exception:
                score = "N/A"

            result["Score"] = score
            result["Status"] = "OK" if score != "N/A" else "PARTIAL"
            result["Message"] = "Test finished"

            # redirect to dashboard so logout is stable
            try:
                driver.get(DASHBOARD_URL)
            except Exception:
                pass

            return result

        except Exception as e:
            result["Message"] = f"Finish failed: {e}"
            return result

    except Exception as outer_e:
        result["Message"] = f"Unhandled error: {outer_e}"
        return result

    finally:
        try:
            # попытка надёжного выхода
            if driver:
                try:
                    # клик по кнопке выхода
                    btn = WebDriverWait(driver, 3).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Выйти из системы')]")))
                    driver.execute_script("arguments[0].click();", btn)
                except Exception:
                    pass
                try:
                    driver.quit()
                except Exception:
                    pass
        except Exception:
            pass


# --------- MAIN (главный процесс) ----------
def main():
    excel = Path(EXCEL_FILE)
    if not excel.exists():
        print("❌ Excel файл не найден:", excel)
        sys.exit(1)

    df = pd.read_excel(excel, engine="openpyxl", dtype=str).fillna("")
    # ожидаемые колонки: IIN, Email, Lastname, Firstname
    accounts: List[Dict[str, str]] = []
    for _, row in df.iterrows():
        email = str(row.get("Email", "")).strip()
        iin = str(row.get("IIN", "")).strip()
        lastname = str(row.get("Lastname", "")).strip()
        firstname = str(row.get("Firstname", "")).strip()
        fullname = f"{lastname} {firstname}".strip()
        if not email:
            continue
        accounts.append({"IIN": iin, "Email": email, "FullName": fullname})

    if not accounts:
        print("Нет аккаунтов для обработки.")
        return

    # Загрузим уже существующие результаты, чтобы не дублировать
    completed_emails = set()
    results_rows: List[Dict[str, Any]] = []
    if RESULTS_FILE.exists():
        prev = pd.read_excel(RESULTS_FILE, engine="openpyxl", dtype=str).fillna("")
        for _, r in prev.iterrows():
            results_rows.append(r.to_dict())
            if r.get("Status") in ("DONE", "OK"):
                completed_emails.add(str(r.get("Email", "")).strip())

    # Фильтруем аккаунты, которые уже сданы
    to_process = [a for a in accounts if a["Email"] not in completed_emails]
    print(f"Всего аккаунтов: {len(accounts)}, к обработке: {len(to_process)}, пропускаем {len(completed_emails)} завершённых")

    # запускаем воркеры (процессы) — не больше MAX_WORKERS одновременно
    with concurrent.futures.ProcessPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_account = {executor.submit(worker_take_test, acc): acc for acc in to_process}

        for future in concurrent.futures.as_completed(future_to_account):
            acc = future_to_account[future]
            try:
                res = future.result(timeout=600)  # подстраховка
            except Exception as e:
                res = {"IIN": acc["IIN"], "Email": acc["Email"], "FullName": acc["FullName"],
                       "Status": "FAILED", "Score": "N/A", "Message": f"Worker exception: {e}"}
            # добавляем в список и сразу сохраняем
            results_rows.append(res)
            # сохраняем в test_results.xlsx (перезапись, но главный процесс контролирует запись)
            pd.DataFrame(results_rows).to_excel(RESULTS_FILE, index=False)
            print(f"Результат: {res['Email']} -> {res['Status']} {res.get('Score','')}: {res.get('Message','')}")

    print("✅ Все задачи выполнены. Итоги в", RESULTS_FILE)


if __name__ == "__main__":
    main()

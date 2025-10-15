import time
import re
import sys
import argparse
import concurrent.futures
from pathlib import Path
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# ======================= НАСТРОЙКИ =======================
EXCEL_FILES = [
    r"D:\PyCharmProjects\auto_test\excel_file\1-200.xlsx",
    r"D:\PyCharmProjects\auto_test\excel_file\200-300.xlsx",
    # Добавь сюда другие Excel файлы при необходимости
]
START_ROW = 2
CHROMEDRIVER_PATH = None
HEADLESS = False
DELAY = 0.4

BASE = "https://amlacademy.kz"
REG_URL = BASE + "/finiq/registration"
PHONE = "+77777777878"
ORGANIZATION = "Предприниматель"
PASSWORD = "Aa123456"
CATEGORY_TEXT = "Взрослый, Студент"

SELECTORS = {
    "lastname": (By.NAME, "lastname"),
    "firstname": (By.NAME, "firstname"),
    "middlename": (By.NAME, "middlename"),
    "phone": (By.NAME, "phone"),
    "organization": (By.NAME, "organization"),
    "email": (By.NAME, "email"),
    "password": (By.NAME, "password"),
    "confirm": (By.NAME, "confirmPassword"),
    "region_div": (By.ID, "region"),
    "category_div": (By.ID, "category"),
    "submit_btn": (By.XPATH, "//button[contains(., 'Зарегистрироваться') or @type='submit']"),
}
# ==========================================================


def parse_fio_from_cell(cell_text: str):
    if not isinstance(cell_text, str):
        cell_text = str(cell_text or "")
    m = re.search(r"\(([^)]+)\)", cell_text)
    fio = m.group(1) if m else cell_text
    parts = [p.strip() for p in fio.split() if p.strip()]
    lastname = parts[0] if len(parts) >= 1 else ""
    firstname = parts[1] if len(parts) >= 2 else ""
    middlename = " ".join(parts[2:]) if len(parts) >= 3 else ""
    return lastname, firstname, middlename


def start_driver(driver_path=None, headless=False):
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1200,900")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--lang=ru")
    if driver_path:
        driver = webdriver.Chrome(executable_path=driver_path, options=options)
    else:
        driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    return driver


def safe_find(driver, by, selector, timeout=6):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, selector)))
    except TimeoutException:
        return None


def select_second_last_option(driver, dropdown_div, wait=6):
    driver.execute_script("arguments[0].scrollIntoView(true);", dropdown_div)
    dropdown_div.click()
    time.sleep(0.5)
    try:
        options = WebDriverWait(driver, wait).until(
            EC.presence_of_all_elements_located((By.XPATH, "//li | //div[@role='option']"))
        )
        if len(options) >= 2:
            target = options[-2]
            driver.execute_script("arguments[0].scrollIntoView(true);", target)
            target.click()
            print(f"✅ Выбран предпоследний регион: {target.text.strip()}")
            return True
    except Exception as e:
        print(f"❌ Ошибка при выборе региона: {e}")
    return False


def click_option_in_dropdown(driver, dropdown_div, desired_text, wait=4):
    try:
        dropdown_div.click()
    except Exception:
        return False, "Не удалось кликнуть dropdown"
    xpath_candidates = [
        f"//li[contains(normalize-space(.),'{desired_text}')]",
        f"//div[@role='option' and contains(normalize-space(.),'{desired_text}')]",
        f"//div[contains(normalize-space(.),'{desired_text}')]",
        f"//span[contains(normalize-space(.),'{desired_text}')]",
    ]
    end_time = time.time() + wait
    while time.time() < end_time:
        for xp in xpath_candidates:
            try:
                el = driver.find_element(By.XPATH, xp)
                el.click()
                return True, "ok"
            except Exception:
                pass
        time.sleep(0.2)
    return False, f"Опция '{desired_text}' не найдена"


def register_one(driver, lastname, firstname, middlename, email):
    driver.get(REG_URL)
    time.sleep(1)

    el = safe_find(driver, *SELECTORS["lastname"])
    if not el:
        return False, "lastname not found"
    el.clear()
    el.send_keys(lastname)

    fn = safe_find(driver, *SELECTORS["firstname"])
    if fn:
        fn.clear()
        fn.send_keys(firstname)

    el = safe_find(driver, *SELECTORS["middlename"])
    if el:
        el.clear()
        el.send_keys(middlename)

    el = safe_find(driver, *SELECTORS["phone"])
    if el:
        el.clear()
        el.send_keys(PHONE)

    el = safe_find(driver, *SELECTORS["organization"])
    if el:
        el.clear()
        el.send_keys(ORGANIZATION)

    el = safe_find(driver, *SELECTORS["email"])
    if not el:
        return False, "email not found"
    el.clear()
    el.send_keys(email)

    safe_find(driver, *SELECTORS["password"]).send_keys(PASSWORD)
    safe_find(driver, *SELECTORS["confirm"]).send_keys(PASSWORD)

    reg = safe_find(driver, *SELECTORS["region_div"])
    if reg:
        select_second_last_option(driver, reg)

    cat = safe_find(driver, *SELECTORS["category_div"])
    if cat:
        click_option_in_dropdown(driver, cat, CATEGORY_TEXT)

    btn = safe_find(driver, *SELECTORS["submit_btn"])
    if btn:
        driver.execute_script("arguments[0].scrollIntoView(true);", btn)
        time.sleep(0.3)
        btn.click()
        print("➡️ Нажата кнопка 'Зарегистрироваться'")
    else:
        return False, "Кнопка 'Зарегистрироваться' не найдена"

    try:
        confirm_btn = WebDriverWait(driver, 6).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Подтвердить') or contains(., 'отправить')]"))
        )
        confirm_btn.click()
        print("✅ Нажата кнопка 'Подтвердить и отправить'")
    except TimeoutException:
        pass

    try:
        error_el = WebDriverWait(driver, 3).until(
            EC.presence_of_element_located((By.XPATH, "//p[contains(text(), 'Student with this email already exists')]"))
        )
        if error_el:
            return False, "Пользователь уже зарегистрирован"
    except TimeoutException:
        pass

    time.sleep(2)
    if "registration" not in driver.current_url:
        return True, "ok"
    return False, "остались на странице регистрации"


def process_excel(excel_path: Path):
    print(f"🚀 Запущена обработка файла: {excel_path}")
    df = pd.read_excel(excel_path, engine='openpyxl', dtype=str).fillna("").map(lambda x: str(x).strip())

    col_iin, col_name = None, None
    for c in df.columns:
        low = str(c).lower().strip()
        if any(x in low for x in ["иин", "iin", "бин", "bin"]):
            col_iin = c
        if any(x in low for x in ["фио", "наимен", "ф.и", "наименование"]):
            col_name = c

    if not col_iin or not col_name:
        print(f"❌ Не найдены колонки ИИН/ФИО в {excel_path.name}")
        return

    driver = start_driver(CHROMEDRIVER_PATH, headless=HEADLESS)
    results = []

    try:
        for _, row in df.iterrows():
            iin = str(row[col_iin]).strip().replace(".0", "")
            raw_name = str(row[col_name]).strip()

            if not iin or iin.lower() in ("nan", "none", "null", ""):
                continue

            lastname, firstname, middlename = parse_fio_from_cell(raw_name)
            email = f"{iin}@mail.ru"

            print(f"🧩 {excel_path.name}: {iin} → {lastname} {firstname} {middlename}")
            success, msg = register_one(driver, lastname, firstname, middlename, email)

            results.append({
                "IIN": iin,
                "Email": email,
                "Password": PASSWORD,
                "Lastname": lastname,
                "Firstname": firstname,
                "Middlename": middlename,
                "Status": "OK" if success else "FAILED",
                "Message": msg
            })
            time.sleep(DELAY)
    finally:
        driver.quit()

    result_path = excel_path.with_name(f"generated_{excel_path.stem}.xlsx")
    pd.DataFrame(results).to_excel(result_path, index=False)
    print(f"✅ Результаты сохранены в {result_path}")


def main():
    print("🚀 Запуск многопоточной регистрации...")

    with concurrent.futures.ProcessPoolExecutor(
        max_workers=min(3, len(EXCEL_FILES))
    ) as executor:
        # нельзя использовать lambda в ProcessPoolExecutor (Windows)
        executor.map(process_excel, [Path(f) for f in EXCEL_FILES])

    print("✅ Все процессы завершены.")



if __name__ == "__main__":
    main()

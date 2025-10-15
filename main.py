# -*- coding: utf-8 -*-
"""
register_and_take_test.py
Автоматическая регистрация одного пользователя, вход и переход к тесту.
Настройте CHROMEDRIVER_PATH и при необходимости селекторы (см. комментарии).
Запуск:
  python register_and_take_test.py --iin 020327499511 --fio "ИП \"TURAN INVEST\" (МУХИДДИНОВ МАКСУД ХАЙИТЖАНҰЛЫ)"
Или можно дать excel: --xlsx users.xlsx --row 2
"""

import argparse
import time
import re
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException
import pandas as pd

# Путь к chromedriver (если в PATH, можно оставить None)
CHROMEDRIVER_PATH = None  # e.g. r"C:\tools\chromedriver.exe" or "/usr/local/bin/chromedriver"

# Конфигурация сайта
BASE = "https://amlacademy.kz"
REG_URL = BASE + "/finiq/registration"
LOGIN_URL = BASE + "/finiq/login"
DASH_URL = BASE + "/finiq/dashboard"

# Фиксированные данные по задаче
REGION_TEXT = "г.Туркестан"   # текст, который появляется в селекте региона
CATEGORY_TEXT = "Взрослый, Студент"  # вариант категории
ORG_TEXT = "Предприниматель"
PASSWORD = "Aa123456"
PHONE = "+7 777 777 7878"

# ВАЖНО: ответы на тест. Предположите, что у вас есть список ответов,
# например answers = ["A","C","B", ...] длиной 20. Формат ответа:
# 'A' означает выбрать первый вариант для вопроса, 'B' второй и т.д.
# Заполните ваш список ниже.
ANSWERS = []  # <-- Вставьте ваши 20 ответов, например: ["A","B","C", ...]


def parse_fio_from_cell(cell_text: str):
    """
    Извлекает строку в скобках и разбивает её на Фамилия Имя Отчество.
    Если скобок нет — пытается разделить по пробелам (последовательность: фамилия имя отчество).
    """
    # Ищем содержимое в круглых скобках (первое вхождение)
    m = re.search(r"\(([^\)]+)\)", cell_text)
    if m:
        inside = m.group(1).strip()
        parts = inside.split()
    else:
        # убираем ИП/ип/т.д. и берем последние слова
        cleaned = re.sub(r'(^ИП\s*|^ип\s*|\"|\“|\”)', '', cell_text).strip()
        parts = cleaned.split()
    # Ожидаем минимум ФИО (3 слова). Если больше — берем первые три.
    if len(parts) >= 3:
        fam, name, otch = parts[0], parts[1], " ".join(parts[2:])
    elif len(parts) == 2:
        fam, name, otch = parts[0], parts[1], ""
    elif len(parts) == 1:
        fam, name, otch = parts[0], "", ""
    else:
        fam, name, otch = "", "", ""
    return fam.strip(), name.strip(), otch.strip()


def start_driver():
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # если нужен headless — включите
    options.add_argument("--start-maximized")
    if CHROMEDRIVER_PATH:
        driver = webdriver.Chrome(executable_path=CHROMEDRIVER_PATH, options=options)
    else:
        driver = webdriver.Chrome(options=options)  # ожидает chromedriver в PATH
    driver.implicitly_wait(6)
    return driver


def fill_registration(driver, fam, name, otch, email):
    driver.get(REG_URL)
    wait = WebDriverWait(driver, 10)

    # --- Примеры селекторов — возможно, вам нужно будет подправить их под вашу форму.
    # По атрибутам name/id/placeholder
    def safe_find(by, val, timeout=6):
        try:
            return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, val)))
        except TimeoutException:
            return None

    # Пример: поля "Фамилия", "Имя", "Отчество" могут иметь placeholder или name
    # Подставьте реальные селекторы если надо.
    # 1) Фамилия
    el_fam = safe_find(By.XPATH, "//input[@placeholder='Фамилия']") or safe_find(By.NAME, "last_name") or safe_find(By.ID, "id_last_name")
    if not el_fam:
        raise RuntimeError("Не найдено поле Фамилия. Проверьте селектор.")
    el_fam.clear()
    el_fam.send_keys(fam)

    # 2) Имя
    el_name = safe_find(By.XPATH, "//input[@placeholder='Имя']") or safe_find(By.NAME, "first_name") or safe_find(By.ID, "id_first_name")
    if not el_name:
        raise RuntimeError("Не найдено поле Имя. Проверьте селектор.")
    el_name.clear()
    el_name.send_keys(name)

    # 3) Отчество
    el_otch = safe_find(By.XPATH, "//input[@placeholder='Отчество']") or safe_find(By.NAME, "patronymic") or safe_find(By.ID, "id_patronymic")
    if el_otch:
        el_otch.clear()
        el_otch.send_keys(otch)

    # 4) Телефон
    el_phone = safe_find(By.XPATH, "//input[contains(@placeholder,'Телефон')]") or safe_find(By.NAME, "phone") or safe_find(By.ID, "id_phone")
    if el_phone:
        el_phone.clear()
        el_phone.send_keys(PHONE)

    # 5) Регион (селект)
    # пытаемся найти select/выпадающий список с текстом региона
    try:
        # сначала поиск тега select
        select_el = driver.find_element(By.XPATH, "//select[contains(@name,'region') or contains(@id,'region')]")
        s = Select(select_el)
        # ищем опцию по видимому тексту
        s.select_by_visible_text(REGION_TEXT)
    except Exception:
        # альтернативно — кликаем кастомный dropdown и выбираем пункт по тексту
        try:
            dd = driver.find_element(By.XPATH, "//div[contains(@class,'region') or contains(.,'Регион')]")
            dd.click()
            opt = WebDriverWait(driver,3).until(EC.element_to_be_clickable((By.XPATH, f"//li[contains(., '{REGION_TEXT}')]")))
            opt.click()
        except Exception:
            print("Внимание: не удалось выбрать регион автоматически — возможно нужно вручную выбрать или поправить селектор.")

    # 6) Организация (просто текст)
    el_org = safe_find(By.XPATH, "//input[contains(@placeholder,'Организация')]") or safe_find(By.NAME, "organization")
    if el_org:
        el_org.clear()
        el_org.send_keys(ORG_TEXT)

    # 7) Email
    el_email = safe_find(By.XPATH, "//input[contains(@placeholder,'Email')]") or safe_find(By.NAME, "email") or safe_find(By.ID, "id_email")
    if not el_email:
        raise RuntimeError("Не найдено поле Email. Проверьте селектор.")
    el_email.clear()
    el_email.send_keys(email)

    # 8) Пароль и подтверждение
    el_pass = safe_find(By.XPATH, "//input[@type='password' and (contains(@placeholder,'Пароль') or contains(@name,'password'))]") or safe_find(By.NAME, "password1")
    el_pass2 = None
    # пытаемся найти второе поле подтверждения
    inputs = driver.find_elements(By.XPATH, "//input[@type='password']")
    if len(inputs) >= 2:
        el_pass = inputs[0]
        el_pass2 = inputs[1]
    if not el_pass:
        raise RuntimeError("Не найдено поле пароля.")
    el_pass.clear()
    el_pass.send_keys(PASSWORD)
    if el_pass2:
        el_pass2.clear()
        el_pass2.send_keys(PASSWORD)

    # 9) Категория — select или кастомный dropdown
    try:
        sel = driver.find_element(By.XPATH, "//select[contains(@name,'category') or contains(@id,'category')]")
        Select(sel).select_by_visible_text(CATEGORY_TEXT)
    except Exception:
        # кастомный
        try:
            cat_dd = driver.find_element(By.XPATH, "//div[contains(@class,'category') or contains(.,'Категория')]")
            cat_dd.click()
            opt = WebDriverWait(driver,3).until(EC.element_to_be_clickable((By.XPATH, f"//li[contains(., '{CATEGORY_TEXT}')]")))
            opt.click()
        except Exception:
            print("Внимание: не удалось автоматически выбрать категорию — проверьте селектор.")

    # 10) Кнопка регистрации — ищем по тексту "Регистрация" или "Зарегистрироваться"
    try:
        btn = driver.find_element(By.XPATH, "//button[contains(., 'Регистрац') or contains(., 'Зарегистрир')]")
        btn.click()
    except Exception:
        # пробуем другой селектор
        try:
            btn = driver.find_element(By.XPATH, "//input[@type='submit']")
            btn.click()
        except Exception as e:
            print("Не удалось найти кнопку регистрации автоматически:", e)
            return False

    # Ждём редирект / сообщение
    time.sleep(3)
    return True


def login_and_start_test(driver, email):
    driver.get(LOGIN_URL)
    wait = WebDriverWait(driver, 10)

    # поля логина — предполагаем email + password
    try:
        el_email = wait.until(EC.presence_of_element_located((By.XPATH, "//input[contains(@placeholder,'Email') or contains(@name,'email')]")))
        el_pass = driver.find_element(By.XPATH, "//input[@type='password' and (contains(@name,'password') or contains(@placeholder,'Пароль'))]")
        el_email.clear(); el_email.send_keys(email)
        el_pass.clear(); el_pass.send_keys(PASSWORD)
        # нажать кнопку входа
        btn = driver.find_element(By.XPATH, "//button[contains(., 'Войти') or contains(., 'Вход')]")
        btn.click()
    except Exception as e:
        print("Ошибка при логине:", e)
        return False

    # Перейдём на dashboard
    time.sleep(2)
    driver.get(DASH_URL)
    time.sleep(2)

    # На dashboard — ищем кнопку "Перейти на тест" или аналог
    try:
        btn_test = wait.until(EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Перейти на тест') or //button[contains(., 'Перейти на тест')]")))
        btn_test.click()
    except Exception:
        # возможно ссылка скрыта, попробуем найти ссылку на /test-result/
        link = None
        try:
            link = driver.find_element(By.XPATH, "//a[contains(@href, '/finiq/test-result/')]")
            link.click()
        except Exception:
            print("Не найдено прямой переход к тесту — откройте вручную:", DASH_URL)
            return False

    time.sleep(2)
    # На странице теста — нажимаем "Начать тест"
    try:
        start_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(.,'Начать тест') or contains(., 'Начать')]")))
        start_btn.click()
    except Exception:
        print("Не удалось найти кнопку 'Начать тест' — возможно уже начат или селектор отличается.")
        # продолжим — попробуем автоматом отвечать, если видим вопросы
    time.sleep(2)

    # --- Автоматическое прохождение вопросов ---
    # здесь нужен список ANSWERS длиной примерно 20. Скрипт попытается для каждого вопроса выбрать вариант A/B/C/D.
    if not ANSWERS:
        print("ANSWERS пуст — автоматическое заполнение ответов не выполнится. Введите ваши ответы в массив ANSWERS в скрипте.")
        return True

    # Простейшая логика: для каждого вопроса на странице находим варианты (радио/label/button) и кликаем по индексу.
    for q_index, ans in enumerate(ANSWERS, start=1):
        # конвертируем A->0, B->1, ...
        idx = ord(ans.strip().upper()[0]) - ord('A')
        print(f"Ответ на вопрос {q_index}: {ans} -> индекс {idx}")
        try:
            # Найдём контейнер вопроса (по порядку)
            # примитивный вариант: все блоки вопросов имеют общий класс, например ".question"
            questions = driver.find_elements(By.XPATH, "//div[contains(@class,'question') or contains(@class,'quiz-question')]")
            if len(questions) >= q_index:
                q_block = questions[q_index - 1]
                # внутри ищем варианты — li, label, button, input radio
                options = q_block.find_elements(By.XPATH, ".//label | .//li | .//button | .//input[@type='radio']")
                if not options:
                    # альтернативно — ищем по общему списку вариантов на странице и берём по смещению
                    options = driver.find_elements(By.XPATH, "//label[contains(@class,'answer') or contains(@class,'option')]")
                if options and len(options) > idx:
                    opt = options[idx]
                    try:
                        # если это input radio — кликнуть на него
                        if opt.tag_name.lower() == 'input':
                            opt.click()
                        else:
                            # клик по label/button/li
                            driver.execute_script("arguments[0].scrollIntoView(true);", opt)
                            opt.click()
                    except Exception as e:
                        print("Ошибка клика по опции:", e)
                else:
                    print(f"Не найден вариант {ans} для вопроса {q_index}.")
            else:
                print(f"Вопрос номер {q_index} не найден на странице.")
        except Exception as e:
            print("Ошибка при обработке вопроса:", e)
        time.sleep(0.6)

        # Нажать "Далее" к следующему вопросу, если такой есть
        try:
            next_btn = driver.find_element(By.XPATH, "//button[contains(., 'Далее') or contains(., 'Следующий') or contains(., 'Next')]")
            next_btn.click()
        except Exception:
            # возможно все вопросы на одной странице, или авто переход
            pass
        time.sleep(0.5)

    # Наконец — найти кнопку "Завершить / Отправить" тест
    try:
        finish_btn = driver.find_element(By.XPATH, "//button[contains(., 'Завершить') or contains(., 'Отправить') or contains(., 'Сдать')]")
        finish_btn.click()
    except Exception:
        print("Не найден финальный сабмит — возможно тест сохранился автоматом.")

    print("Готово. Проверьте страницу результатов.")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--iin', help='ИИН (например 020327499511)')
    parser.add_argument('--fio', help='Строка из столбца Наименование/Ф.И.О.')
    parser.add_argument('--xlsx', help='Excel-файл с данными (если хотите взять оттуда)')
    parser.add_argument('--row', type=int, help='Номер строки в Excel (1-based)')
    args = parser.parse_args()

    if not args.iin and not args.xlsx:
        print("Нужно указать --iin или --xlsx --row")
        return

    if args.xlsx:
        df = pd.read_excel(args.xlsx, engine='openpyxl')
        if not args.row:
            print("Для xlsx укажите --row")
            return
        row_idx = args.row - 1
        if row_idx < 0 or row_idx >= len(df):
            print("Неверный номер строки")
            return
        # ожидаем, что колонка с ФИО называется 'Наименование/Ф.И.О.' или похожим
        col_candidates = [c for c in df.columns if 'наимен' in c.lower() or 'фио' in c.lower()]
        if not col_candidates:
            print("Не удалось найти столбец с ФИО в excel. Укажите файл с колонкой 'Наименование/Ф.И.О.'")
            return
        fio_cell = str(df.iloc[row_idx][col_candidates[0]])
        iin = str(df.iloc[row_idx].get('ИИН') or df.iloc[row_idx].get('iin') or args.iin)
        if not iin:
            print("В таблице не найден ИИН в этой строке. Можно передать --iin вручную.")
            return
        fam, name, otch = parse_fio_from_cell(fio_cell)
    else:
        if not args.fio:
            print("Если не используете xlsx — укажите --fio")
            return
        iin = args.iin
        fam, name, otch = parse_fio_from_cell(args.fio)

    # формируем email
    email = f"{iin}@mail.ru"
    print("Будет создан аккаунт:")
    print("Фамилия:", fam, "Имя:", name, "Отчество:", otch)
    print("Email:", email)
    print("Пароль:", PASSWORD)

    # Запускаем Selenium
    driver = start_driver()
    try:
        ok = fill_registration(driver, fam, name, otch, email)
        if not ok:
            print("Ошибка при регистрации — проверьте селекторы и страницу.")
            driver.quit()
            return
        # небольшая пауза, возможно нужно подтвердить почту — если нет, продолжаем
        time.sleep(2)
        ok = login_and_start_test(driver, email)
        if not ok:
            print("Что-то не получилось на этапе логина/теста. Проверьте вывод.")
    finally:
        print("Сценарий завершён. Закрываем браузер через 5 секунд.")
        time.sleep(5)
        driver.quit()


if __name__ == "__main__":
    main()

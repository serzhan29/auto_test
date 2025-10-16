import re
from pathlib import Path
import pandas as pd
from django.core.management.base import BaseCommand
from main.models import UserAccount


class Command(BaseCommand):
    help = "Импорт пользователей из Excel (берёт №, ИИН/БИН, ФИО из скобок)"

    def handle(self, *args, **options):
        # 📂 Укажи здесь путь к Excel-файлу (относительно manage.py или абсолютный)
        excel_path = Path("main/management/commands/excel_date/ИП-ТОО Кентау.xlsx")


        if not excel_path.exists():
            self.stderr.write(self.style.ERROR(f"❌ Файл не найден: {excel_path.resolve()}"))
            return

        # Читаем Excel-файл
        df = pd.read_excel(excel_path, engine="openpyxl", dtype=str).fillna("")

        # Определяем нужные колонки
        col_num, col_iin, col_name = None, None, None
        for c in df.columns:
            low = str(c).lower()
            if "иин" in low or "бин" in low:
                col_iin = c
            elif "наимен" in low or "фио" in low:
                col_name = c
            elif "№" in low or "номер" in low:
                col_num = c

        if not col_iin or not col_name:
            self.stderr.write(self.style.ERROR("Не найдены нужные колонки в Excel!"))
            return

        added = 0
        skipped = 0

        for _, row in df.iterrows():
            iin = str(row.get(col_iin, "")).strip()
            name_raw = str(row.get(col_name, "")).strip()

            # Извлекаем текст внутри скобок
            match = re.search(r"\(([^)]+)\)", name_raw)
            full_name = match.group(1).strip() if match else name_raw.strip()

            if not iin or not full_name:
                continue

            email = f"{iin}@mail.ru"

            # Проверяем, есть ли уже пользователь
            if UserAccount.objects.filter(iin=iin).exists():
                skipped += 1
                continue

            # Создаём нового пользователя
            UserAccount.objects.create(
                iin=iin,
                full_name=full_name,
                email=email,
                password="Aa123456",
                status="pending"
            )
            added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Импорт завершён: добавлено {added}, пропущено {skipped}\n"
                f"📄 Источник: {excel_path.resolve()}"
            )
        )


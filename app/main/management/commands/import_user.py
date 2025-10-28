import re
from pathlib import Path
import pandas as pd
from django.core.management.base import BaseCommand
from main.models import UserAccount


class Command(BaseCommand):
    help = "Импорт данных (БИН и ФИО руководителя) из первых 8 листов Excel"

    def handle(self, *args, **options):
        # 📂 Укажи путь к Excel-файлу
        excel_path = Path("main/management/commands/excel_date/Копия СПИСОК_ДЛЯ_ОТДЕЛОВ_АКИМАТА_общий_(1)(1).xls")

        if not excel_path.exists():
            self.stderr.write(self.style.ERROR(f"❌ Файл не найден: {excel_path.resolve()}"))
            return

        # Считываем имена всех листов
        xls = pd.ExcelFile(excel_path)

        # Берём только первые 8
        sheet_names = xls.sheet_names[:10]

        added = 0
        skipped = 0

        for sheet in sheet_names:
            self.stdout.write(self.style.NOTICE(f"📄 Обработка листа: {sheet}"))
            df = pd.read_excel(xls, sheet_name=sheet, dtype=str).fillna("")

            # Поиск колонок
            col_bin, col_name = None, None
            for c in df.columns:
                low = str(c).lower()
                if "бин" in low:
                    col_bin = c
                elif "басшы" in low or "фио" in low or "таә" in low:
                    col_name = c

            if not col_bin or not col_name:
                self.stderr.write(self.style.WARNING(f"⚠️ Пропущен лист '{sheet}' — нет нужных колонок"))
                continue

            for _, row in df.iterrows():
                bin_val = str(row.get(col_bin, "")).strip()
                name_raw = str(row.get(col_name, "")).strip()

                # Если БИН невалидный или пустой — пропускаем
                if not bin_val or not re.match(r"^\d{12}$", bin_val):
                    continue

                full_name = name_raw.strip()
                if not full_name:
                    continue

                email = f"{bin_val}@mail.ru"

                # Проверяем дубликаты
                if UserAccount.objects.filter(iin=bin_val).exists():
                    skipped += 1
                    continue

                # Создаём новую запись
                UserAccount.objects.create(
                    iin=bin_val,  # можно оставить поле iin, если в модели нет отдельного "bin"
                    full_name=full_name,
                    email=email,
                    password="Aa123456",
                    status="pending"
                )
                added += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"✅ Импорт завершён: добавлено {added}, пропущено {skipped}\n"
                f"📂 Источник: {excel_path.resolve()}"
            )
        )

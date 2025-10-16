from django.core.management.base import BaseCommand
from main.models import UserAccount

class Command(BaseCommand):
    help = "Добавляет +1 к каждому ИИН и корректирует email"

    def handle(self, *args, **options):
        users = UserAccount.objects.all()
        updated = 0

        for user in users:
            try:
                # Пробуем преобразовать ИИН в число и прибавить 1
                new_iin = str(int(user.iin) + 1)

                # email = старый_без_iin + новый_iin@mail.ru
                if "@mail.ru" in user.email:
                    email_part = user.email.split("@")[0]
                    # если email был в виде <iin>@mail.ru, заменяем на новый
                    if email_part.isdigit():
                        new_email = f"{new_iin}@mail.ru"
                    else:
                        # иначе добавляем к старому email числовой хвост
                        new_email = f"{email_part}_{new_iin}@mail.ru"
                else:
                    new_email = f"{new_iin}@mail.ru"

                # сохраняем
                user.iin = new_iin
                user.email = new_email
                user.save()
                updated += 1

            except Exception as e:
                self.stderr.write(f"⚠️ Ошибка с {user.iin}: {e}")

        self.stdout.write(self.style.SUCCESS(f"✅ Обновлено {updated} пользователей"))

from django.db import models


class UserAccount(models.Model):
    """Основная таблица для хранения пользователей"""
    iin = models.CharField("ИИН", max_length=20, unique=True)
    full_name = models.CharField("ФИО", max_length=255)
    email = models.EmailField("Email", unique=True)
    password = models.CharField("Пароль", max_length=128, default="Aa123456")

    STATUS_CHOICES = [
        ('pending', '🟡 В очереди'),
        ('registered', '🟢 Зарегистрирован'),
        ('tested', '✅ Тест сдан'),
        ('completed', '📄 Сертификат скачан'),
        ('failed', '❌ Ошибка'),
    ]
    status = models.CharField("Статус", max_length=20, choices=STATUS_CHOICES, default='pending')

    score = models.CharField("Результат теста (%)", max_length=10, blank=True, null=True)
    certificate_file = models.CharField("Путь к сертификату", max_length=255, blank=True, null=True)
    message = models.TextField("Комментарий / ошибка", blank=True, null=True)

    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    def __str__(self):
        return f"{self.full_name} ({self.email})"

    class Meta:
        verbose_name = "Пользователь"
        verbose_name_plural = "Пользователи"


class AutomationLog(models.Model):
    """Хранит историю действий над каждым пользователем"""
    user = models.ForeignKey(UserAccount, on_delete=models.CASCADE, related_name="logs")
    stage = models.CharField("Этап", max_length=50)
    success = models.BooleanField("Успешно", default=False)
    message = models.TextField("Сообщение", blank=True, null=True)
    created_at = models.DateTimeField("Дата", auto_now_add=True)

    def __str__(self):
        return f"[{self.stage}] {self.user.full_name}"

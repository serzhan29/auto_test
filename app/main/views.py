from django.shortcuts import render, redirect
from django.contrib import messages
from django.db.models import Count
from .models import UserAccount
from . import tasks


def dashboard(request):
    """Главная панель со статистикой"""
    stats = (
        UserAccount.objects.values("status")
        .annotate(count=Count("id"))
        .order_by()
    )

    total = UserAccount.objects.count()
    return render(request, "automation/dashboard.html", {"stats": stats, "total": total})


def start_registration(request):
    """Запуск регистрации пользователей"""
    count = tasks.run_registration()
    messages.success(request, f"Регистрация завершена для {count} пользователей.")
    return redirect("dashboard")


def start_testing(request):
    """Запуск автоматической сдачи тестов"""
    count = tasks.run_tests()
    messages.success(request, f"Тестирование завершено для {count} пользователей.")
    return redirect("dashboard")


def start_downloads(request):
    """Запуск скачивания сертификатов"""
    count = tasks.run_downloads()
    messages.success(request, f"Сертификаты скачаны для {count} пользователей.")
    return redirect("dashboard")

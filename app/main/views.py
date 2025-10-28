# main/views.py
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.db.models import Q
from .models import UserAccount
from . import registration_manager, test_manager, certificate_manager


def dashboard(request):
    query = request.GET.get("q", "")
    sort = request.GET.get("sort", "id")

    users = UserAccount.objects.all()

    # фильтрация по поиску
    if query:
        users = users.filter(
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(iin__icontains=query)
        )

    # агрегированная статистика
    total_users = users.count()
    reg_count = users.filter(is_registered=True).count()
    test_count = users.filter(is_tested=True).count()
    dl_count = users.filter(is_downloaded=True).count()
    err_count = users.filter(has_error=True).count()
    pending_count = total_users - (reg_count + test_count + dl_count + err_count)

    # выборки по категориям
    registered_users = users.filter(is_registered=True).order_by("-id")[:10]
    tested_users = users.filter(is_tested=True).order_by("-id")[:10]
    downloaded_users = users.filter(is_downloaded=True).order_by("-id")[:10]
    error_users = users.filter(has_error=True).order_by("-id")  # 👈 пользователи с ошибками

    # статусы фоновых процессов
    reg_stats = registration_manager.get_status()
    test_stats = test_manager.get_status()
    download_stats = certificate_manager.get_status()

    context = {
        "total_users": total_users,
        "reg_count": reg_count,
        "test_count": test_count,
        "dl_count": dl_count,
        "err_count": err_count,
        "pending_count": pending_count,
        "registered_users": registered_users,
        "tested_users": tested_users,
        "downloaded_users": downloaded_users,
        "error_users": error_users,  # 👈 передаём в шаблон
        "query": query,
        "sort": sort,
        "reg_stats": reg_stats,
        "test_stats": test_stats,
        "download_stats": download_stats,
    }

    return render(request, "main/dashboard.html", context)




# ===== Управление регистрацией =====
def start_registration_view(request):
    registration_manager.start_registration()
    return redirect("dashboard")

def stop_registration_view(request):
    registration_manager.stop_registration()
    return redirect("dashboard")


# ===== Управление тестированием =====
def start_testing_view(request):
    test_manager.start_testing()
    return redirect("dashboard")

def stop_testing_view(request):
    test_manager.stop_testing()
    return redirect("dashboard")


# ===== Управление сертификатами =====
def start_downloads_view(request):
    certificate_manager.start_downloading()
    return redirect("dashboard")

def stop_downloads_view(request):
    certificate_manager.stop_downloading()
    return redirect("dashboard")

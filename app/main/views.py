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

    # сортировка
    if sort == "errors":
        users = users.filter(has_error=True)
    elif sort == "registered":
        users = users.filter(is_registered=True)
    elif sort == "tested":
        users = users.filter(is_tested=True)
    elif sort == "downloaded":
        users = users.filter(is_downloaded=True)
    else:
        users = users.order_by("-id")

    latest_users = users[:5]

    # 👇 теперь добавляем все три состояния Selenium-процессов
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
        "latest_users": latest_users,
        "query": query,
        "sort": sort,

        # передаём три отдельных состояния
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

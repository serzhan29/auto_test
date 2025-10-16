# main/views.py
from django.http import JsonResponse
from django.shortcuts import render
from django.db.models import Q
from .models import UserAccount
from .registration_manager import start_registration, stop_registration, get_status

def dashboard(request):
    query = request.GET.get("q", "")
    sort = request.GET.get("sort", "id")  # сортировка

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
        "status": get_status(),  # состояние Selenium-процесса
    }
    return render(request, "main/dashboard.html", context)


def start_process(request):
    ok = start_registration()
    return JsonResponse({"ok": ok})


def stop_process(request):
    stop_registration()
    return JsonResponse({"ok": True})

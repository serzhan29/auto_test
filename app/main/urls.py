# main/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),

    # Регистрация
    path("start-registration/", views.start_registration_view, name="start_registration"),
    path("stop-registration/", views.stop_registration_view, name="stop_registration"),

    # Тестирование
    path("start-testing/", views.start_testing_view, name="start_testing"),
    path("stop-testing/", views.stop_testing_view, name="stop_testing"),

    # Сертификаты
    path("start-downloads/", views.start_downloads_view, name="start_downloads"),
    path("stop-downloads/", views.stop_downloads_view, name="stop_downloads"),
]

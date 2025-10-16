# main/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("start/", views.start_process, name="start_process"),
    path("stop/", views.stop_process, name="stop_process"),
]

from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("start/registration/", views.start_registration, name="start_registration"),
    path("start/testing/", views.start_testing, name="start_testing"),
    path("start/downloads/", views.start_downloads, name="start_downloads"),
]

from django.contrib import admin
from .models import UserAccount, AutomationLog


admin.site.register(UserAccount)
admin.site.register(AutomationLog)


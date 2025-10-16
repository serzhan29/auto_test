from django.contrib import admin
from .models import UserAccount, AutomationLog


class UserAccountAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "email", "iin"]



admin.site.register(UserAccount, UserAccountAdmin)
admin.site.register(AutomationLog)


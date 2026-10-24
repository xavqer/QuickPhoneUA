from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, PhoneVerificationChallenge


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ("Contact", {"fields": ("phone", "telegram_handle", "phone_verified_at")}),
    )
    list_display = ("username", "email", "is_staff", "is_active", "phone", "phone_verified_at")
    search_fields = ("username", "email", "phone", "telegram_handle")
    readonly_fields = ("phone_verified_at",)


@admin.register(PhoneVerificationChallenge)
class PhoneVerificationChallengeAdmin(admin.ModelAdmin):
    list_display = ("id", "purpose", "phone", "user", "attempts_count", "created_at", "expires_at", "consumed_at")
    list_filter = ("purpose", "created_at", "expires_at", "consumed_at")
    search_fields = ("phone", "user__username", "user__phone", "sent_message_id")

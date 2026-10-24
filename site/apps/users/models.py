from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    phone = models.CharField(max_length=20, blank=True)
    telegram_handle = models.CharField(max_length=100, blank=True)
    phone_verified_at = models.DateTimeField(null=True, blank=True)


class PhoneVerificationChallenge(models.Model):
    class Purpose(models.TextChoices):
        REGISTRATION = "registration", "Реєстрація"
        LOGIN = "login", "Вхід"
        PASSWORD_RESET = "password_reset", "Скидання пароля"
        PHONE_CHANGE = "phone_change", "Зміна номера"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.CASCADE, related_name="phone_verification_challenges",
    )
    purpose = models.CharField(max_length=32, choices=Purpose.choices)
    phone = models.CharField(max_length=20)
    code_hash = models.CharField(max_length=128)
    payload = models.JSONField(default=dict, blank=True)
    attempts_count = models.PositiveSmallIntegerField(default=0)
    max_attempts = models.PositiveSmallIntegerField(default=5)
    sent_message_id = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("purpose", "phone", "created_at")),
            models.Index(fields=("user", "purpose", "created_at")),
        ]

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def remaining_attempts(self):
        return max(self.max_attempts - self.attempts_count, 0)

    def set_code(self, raw_code):
        self.code_hash = make_password(raw_code)

    def check_code(self, raw_code):
        return check_password(raw_code or "", self.code_hash)

    def consume(self):
        if self.is_consumed:
            return
        self.consumed_at = timezone.now()
        self.save(update_fields=["consumed_at"])

    def expire(self):
        now = timezone.now()
        if self.expires_at > now:
            self.expires_at = now
            self.save(update_fields=["expires_at"])

    def register_failed_attempt(self):
        self.attempts_count += 1
        update_fields = ["attempts_count"]
        if self.attempts_count >= self.max_attempts and not self.is_expired:
            self.expires_at = timezone.now()
            update_fields.append("expires_at")
        self.save(update_fields=update_fields)

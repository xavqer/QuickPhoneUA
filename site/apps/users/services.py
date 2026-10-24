import math
import secrets
from datetime import timedelta
from functools import wraps

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.utils import timezone

from .models import PhoneVerificationChallenge
from .sms_client import SmsClubClient


class PhoneVerificationError(Exception):
    pass


def build_unique_username(phone, user_model=None, exclude_user_id=None):
    user_model = user_model or get_user_model()
    users = user_model.objects.all()
    if exclude_user_id:
        users = users.exclude(pk=exclude_user_id)

    username = phone
    if not users.filter(username=username).exists():
        return username

    suffix = 2
    while users.filter(username=f"{phone}_{suffix}").exists():
        suffix += 1
    return f"{phone}_{suffix}"


def generate_verification_code():
    test_code = settings.SMS_VERIFICATION_TEST_CODE.strip()
    if test_code:
        return test_code
    length = max(settings.SMS_VERIFICATION_CODE_LENGTH, 4)
    return "".join(secrets.choice("0123456789") for _ in range(length))


def get_resend_wait_seconds(challenge):
    cooldown_seconds = max(settings.SMS_VERIFICATION_RESEND_SECONDS, 0)
    available_at = challenge.created_at + timedelta(seconds=cooldown_seconds)
    delta_seconds = (available_at - timezone.now()).total_seconds()
    return max(math.ceil(delta_seconds), 0)


def requires_login_verification(user):
    threshold_days = settings.SMS_LOGIN_REVERIFY_DAYS
    if threshold_days <= 0 or user.last_login is None:
        return True
    return user.last_login <= timezone.now() - timedelta(days=threshold_days)


def start_registration_verification(cleaned_data, next_url="", client=None):
    payload = {
        "first_name": cleaned_data["first_name"],
        "last_name": cleaned_data["last_name"],
        "phone": cleaned_data["phone"],
        "password_hash": make_password(cleaned_data["password1"]),
        "next_url": next_url or "",
    }
    return start_phone_verification(
        purpose=PhoneVerificationChallenge.Purpose.REGISTRATION, phone=cleaned_data["phone"],
        payload=payload, client=client,
    )


def start_login_verification(user, next_url="", client=None):
    return start_phone_verification(
        purpose=PhoneVerificationChallenge.Purpose.LOGIN, phone=user.phone, user=user,
        payload={"next_url": next_url or ""}, client=client,
    )


def start_password_reset_verification(user, client=None):
    return start_phone_verification(purpose=PhoneVerificationChallenge.Purpose.PASSWORD_RESET, phone=user.phone, user=user, client=client)


def start_phone_change_verification(user, new_phone, client=None):
    return start_phone_verification(purpose=PhoneVerificationChallenge.Purpose.PHONE_CHANGE, phone=new_phone, user=user, client=client)


def start_phone_verification(purpose, phone, user=None, payload=None, client=None):
    now = timezone.now()
    lifetime_minutes = max(settings.SMS_VERIFICATION_CODE_TTL_MINUTES, 1)
    PhoneVerificationChallenge.objects.filter(
        purpose=purpose, phone=phone, user=user, consumed_at__isnull=True, expires_at__gt=now,
    ).update(expires_at=now)

    raw_code = generate_verification_code()
    challenge = PhoneVerificationChallenge(
        user=user, purpose=purpose, phone=phone, payload=payload or {},
        expires_at=now + timedelta(minutes=lifetime_minutes),
    )
    challenge.set_code(raw_code)
    challenge.save()

    result = (client or SmsClubClient()).send_sms(phone=phone, message=f"Код підтвердження QuickPhoneUA: {raw_code}")
    if not result["ok"]:
        challenge.delete()
        raise PhoneVerificationError(result["message"])

    challenge.sent_message_id = result.get("message_id", "")
    challenge.save(update_fields=["sent_message_id"])
    return challenge


def resend_phone_verification(challenge, client=None):
    wait_seconds = get_resend_wait_seconds(challenge)
    if wait_seconds > 0:
        raise PhoneVerificationError(f"Повторний код можна надіслати через {wait_seconds} с.")
    return start_phone_verification(
        purpose=challenge.purpose, phone=challenge.phone, user=challenge.user,
        payload=challenge.payload, client=client,
    )


def _verified_challenge(purpose):
    def decorate(confirm):
        @wraps(confirm)
        def wrapped(challenge, raw_code, *args, **kwargs):
            if challenge.purpose != purpose:
                raise PhoneVerificationError("Некоректний тип підтвердження.")
            with transaction.atomic():
                challenge = PhoneVerificationChallenge.objects.select_for_update().get(pk=challenge.pk)
                try:
                    _validate_challenge(challenge, raw_code, purpose)
                except PhoneVerificationError as exc:
                    error = exc
                else:
                    return confirm(challenge, raw_code, *args, **kwargs)
            # Raise after committing failed attempts, not inside their transaction.
            raise error
        return wrapped
    return decorate


@_verified_challenge(PhoneVerificationChallenge.Purpose.REGISTRATION)
def confirm_registration(challenge, raw_code):
    payload = challenge.payload or {}
    phone = payload.get("phone") or challenge.phone
    password_hash = (payload.get("password_hash") or "").strip()
    if not password_hash:
        raise PhoneVerificationError("Сесію реєстрації втрачено. Почніть реєстрацію ще раз.")

    user_model = get_user_model()
    if user_model.objects.filter(phone=phone).exists():
        raise PhoneVerificationError("Користувач з цим номером уже існує.")

    user = user_model(
        first_name=(payload.get("first_name") or "").strip(),
        last_name=(payload.get("last_name") or "").strip(),
        phone=phone,
        username=build_unique_username(phone, user_model=user_model),
        phone_verified_at=timezone.now(),
    )
    user.password = password_hash
    user.save()

    challenge.consume()
    return user, (payload.get("next_url") or "").strip()


@_verified_challenge(PhoneVerificationChallenge.Purpose.LOGIN)
def confirm_login_verification(challenge, raw_code):
    if challenge.user is None or not challenge.user.is_active:
        raise PhoneVerificationError("Не вдалося підтвердити вхід для цього акаунта.")

    challenge.consume()
    return challenge.user, ((challenge.payload or {}).get("next_url") or "").strip()


@_verified_challenge(PhoneVerificationChallenge.Purpose.PASSWORD_RESET)
def confirm_password_reset(challenge, raw_code, new_password):
    if challenge.user is None or not challenge.user.is_active:
        raise PhoneVerificationError("Не вдалося скинути пароль для цього акаунта.")

    user = challenge.user
    user.set_password(new_password)
    user.save(update_fields=["password"])
    challenge.consume()
    return user


@_verified_challenge(PhoneVerificationChallenge.Purpose.PHONE_CHANGE)
def confirm_phone_change(challenge, raw_code):
    if challenge.user is None or not challenge.user.is_active:
        raise PhoneVerificationError("Не вдалося змінити номер телефону для цього акаунта.")

    user_model = get_user_model()
    if user_model.objects.filter(phone=challenge.phone).exclude(pk=challenge.user_id).exists():
        raise PhoneVerificationError("Користувач з цим номером уже існує.")

    user = challenge.user
    user.phone = challenge.phone
    user.username = build_unique_username(challenge.phone, user_model=user_model, exclude_user_id=user.pk)
    user.phone_verified_at = timezone.now()
    user.save(update_fields=["phone", "username", "phone_verified_at"])
    challenge.consume()
    return user


def _validate_challenge(challenge, raw_code, purpose):
    if challenge.purpose != purpose:
        raise PhoneVerificationError("Некоректний тип підтвердження.")
    if challenge.is_consumed:
        raise PhoneVerificationError("Цей код уже використано. Надішліть новий код.")
    if challenge.remaining_attempts <= 0:
        raise PhoneVerificationError("Ліміт спроб вичерпано. Надішліть новий код.")
    if challenge.is_expired:
        raise PhoneVerificationError("Термін дії коду минув. Надішліть новий код.")
    if not challenge.check_code(raw_code):
        challenge.register_failed_attempt()
        if challenge.remaining_attempts <= 0:
            raise PhoneVerificationError("Ліміт спроб вичерпано. Надішліть новий код.")
        raise PhoneVerificationError(f"Невірний код. Залишилося спроб: {challenge.remaining_attempts}.")

from decimal import Decimal

from django.conf import settings
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.orders.models import Order

from .forms import (
    PasswordResetConfirmForm,
    PasswordResetRequestForm,
    PhoneChangeRequestForm,
    PhoneLoginForm,
    PhoneRegistrationForm,
    ProfileUpdateForm,
    SmsCodeForm,
)
from .models import PhoneVerificationChallenge
from .phone import format_ua_phone_display
from .services import (
    PhoneVerificationError,
    confirm_login_verification,
    confirm_password_reset,
    confirm_phone_change,
    confirm_registration,
    get_resend_wait_seconds,
    requires_login_verification,
    resend_phone_verification,
    start_login_verification,
    start_password_reset_verification,
    start_phone_change_verification,
    start_registration_verification,
)


VERIFICATION_SESSION_KEYS = {
    PhoneVerificationChallenge.Purpose.REGISTRATION: "users_registration_challenge_id",
    PhoneVerificationChallenge.Purpose.LOGIN: "users_login_challenge_id",
    PhoneVerificationChallenge.Purpose.PASSWORD_RESET: "users_password_reset_challenge_id",
    PhoneVerificationChallenge.Purpose.PHONE_CHANGE: "users_phone_change_challenge_id",
}


def _resolve_next_url(request):
    return _get_safe_next_url(request) or reverse("home")


def _get_safe_next_url(request):
    next_url = request.POST.get("next") or request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(url=next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return next_url
    return ""


def _registration_initial_from_request(request):
    return {
        "first_name": (request.GET.get("first_name") or "").strip(),
        "last_name": (request.GET.get("last_name") or "").strip(),
        "phone": (request.GET.get("phone") or "").strip(),
    }


def _registration_initial_from_challenge(challenge):
    payload = challenge.payload or {}
    return {
        "first_name": (payload.get("first_name") or "").strip(),
        "last_name": (payload.get("last_name") or "").strip(),
        "phone": (payload.get("phone") or challenge.phone or "").strip(),
    }


def register_view(request):
    if request.user.is_authenticated:
        return redirect(_resolve_next_url(request))

    if not settings.REGISTRATION_ENABLED:
        return render(request, "users/register.html", {"registration_disabled": True}, status=403)

    if not settings.SMS_VERIFICATION_ENABLED:
        _clear_all_verification_sessions(request)
        form = PhoneRegistrationForm(request.POST or None, initial=_registration_initial_from_request(request))
        next_url = _get_safe_next_url(request)
        if request.method == "POST" and form.is_valid():
            user = form.save()
            login(request, user)
            return redirect(_resolve_next_url(request))
        return render(request, "users/register.html", {
            "form": form,
            "next_url": next_url,
            "verification": None,
            "sms_verification_enabled": False,
        })

    challenge = _get_verification_challenge(request, PhoneVerificationChallenge.Purpose.REGISTRATION)
    next_url = _get_safe_next_url(request)
    verification = None

    if challenge is not None:
        next_url = ((challenge.payload or {}).get("next_url") or next_url).strip()
        form = PhoneRegistrationForm(initial=_registration_initial_from_challenge(challenge))
        verification_form = SmsCodeForm()
        resend_success = False

        if request.method == "POST":
            action = request.POST.get("verification_action")
            if action == "cancel":
                _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.REGISTRATION)
                return redirect("users:register")
            if action == "resend":
                challenge, resend_success = _resend_verification_challenge(request, challenge, verification_form)
            elif action == "verify":
                verification_form = SmsCodeForm(request.POST)
                if verification_form.is_valid():
                    try:
                        user, resolved_next_url = confirm_registration(challenge, verification_form.cleaned_data["code"])
                    except PhoneVerificationError as exc:
                        verification_form.add_error("code", str(exc))
                    else:
                        _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.REGISTRATION)
                        login(request, user)
                        return redirect(resolved_next_url or reverse("home"))

        verification = _build_code_overlay_context(
            challenge=challenge,
            form=verification_form,
            resend_success=resend_success,
            eyebrow="SMS-код",
            heading="Підтвердіть номер телефону",
            description="Ми надіслали код на цей номер. Введіть його, щоб завершити реєстрацію.",
            submit_label="Завершити реєстрацію",
        )
    else:
        form = PhoneRegistrationForm(request.POST or None, initial=_registration_initial_from_request(request))
        if request.method == "POST" and form.is_valid():
            try:
                challenge = start_registration_verification(form.cleaned_data, next_url=next_url)
            except PhoneVerificationError as exc:
                form.add_error(None, str(exc))
            else:
                _store_verification_challenge(request, PhoneVerificationChallenge.Purpose.REGISTRATION, challenge)
                return redirect("users:register")

    return render(request, "users/register.html", {
        "form": form,
        "next_url": next_url,
        "verification": verification,
        "sms_verification_enabled": True,
    })


def register_verify_view(request):
    return redirect("users:register")


def login_view(request):
    if request.user.is_authenticated:
        return redirect(_resolve_next_url(request))

    if not settings.SMS_VERIFICATION_ENABLED:
        _clear_all_verification_sessions(request)
        form = PhoneLoginForm(request.POST or None, request=request)
        next_url = _get_safe_next_url(request)
        if request.method == "POST" and form.is_valid():
            login(request, form.get_user())
            return redirect(next_url or reverse("home"))
        return render(request, "users/login.html", {
            "form": form,
            "next_url": next_url,
            "verification": None,
            "sms_verification_enabled": False,
        })

    challenge = _get_verification_challenge(request, PhoneVerificationChallenge.Purpose.LOGIN)
    next_url = _get_safe_next_url(request)
    verification = None

    if challenge is not None:
        next_url = ((challenge.payload or {}).get("next_url") or next_url).strip()
        form = PhoneLoginForm(request=request, initial={"phone": challenge.phone})
        verification_form = SmsCodeForm()
        resend_success = False

        if request.method == "POST":
            action = request.POST.get("verification_action")
            if action == "cancel":
                _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.LOGIN)
                return redirect("users:login")
            if action == "resend":
                challenge, resend_success = _resend_verification_challenge(request, challenge, verification_form)
            elif action == "verify":
                verification_form = SmsCodeForm(request.POST)
                if verification_form.is_valid():
                    try:
                        user, resolved_next_url = confirm_login_verification(challenge, verification_form.cleaned_data["code"])
                    except PhoneVerificationError as exc:
                        verification_form.add_error("code", str(exc))
                    else:
                        _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.LOGIN)
                        login(request, user)
                        return redirect(resolved_next_url or reverse("home"))

        verification = _build_code_overlay_context(
            challenge=challenge,
            form=verification_form,
            resend_success=resend_success,
            eyebrow="Захист акаунта",
            heading="Підтвердіть вхід кодом",
            description="Для цього входу потрібне додаткове підтвердження через SMS.",
            submit_label="Підтвердити вхід",
        )
    else:
        form = PhoneLoginForm(request.POST or None, request=request)
        if request.method == "POST" and form.is_valid():
            user = form.get_user()
            if requires_login_verification(user):
                try:
                    challenge = start_login_verification(user, next_url=next_url)
                except PhoneVerificationError as exc:
                    form.add_error(None, str(exc))
                else:
                    _store_verification_challenge(request, PhoneVerificationChallenge.Purpose.LOGIN, challenge)
                    return redirect("users:login")
            else:
                login(request, user)
                return redirect(next_url or reverse("home"))

    return render(request, "users/login.html", {
        "form": form,
        "next_url": next_url,
        "verification": verification,
        "sms_verification_enabled": True,
    })


def login_verify_view(request):
    return redirect("users:login")


def password_reset_request_view(request):
    if not settings.SMS_VERIFICATION_ENABLED:
        _clear_all_verification_sessions(request)
        return redirect("users:login")

    challenge = _get_verification_challenge(request, PhoneVerificationChallenge.Purpose.PASSWORD_RESET)
    verification = None

    if challenge is not None:
        form = PasswordResetRequestForm(initial={"phone": challenge.phone})
        verification_form = PasswordResetConfirmForm(user=challenge.user)
        resend_success = False

        if request.method == "POST":
            action = request.POST.get("verification_action")
            if action == "cancel":
                _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.PASSWORD_RESET)
                return redirect("users:password_reset_request")
            if action == "resend":
                challenge, resend_success = _resend_verification_challenge(request, challenge, verification_form)
            elif action == "verify":
                verification_form = PasswordResetConfirmForm(request.POST, user=challenge.user)
                if verification_form.is_valid():
                    try:
                        user = confirm_password_reset(
                            challenge,
                            verification_form.cleaned_data["code"],
                            verification_form.cleaned_data["password1"],
                        )
                    except PhoneVerificationError as exc:
                        verification_form.add_error("code", str(exc))
                    else:
                        _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.PASSWORD_RESET)
                        login(request, user)
                        return redirect(f"{reverse('users:profile')}?password_reset=1")

        verification = {
            "form": verification_form,
            "phone_display": format_ua_phone_display(challenge.phone),
            "resend_success": resend_success,
            "resend_wait_seconds": get_resend_wait_seconds(challenge),
        }
    else:
        form = PasswordResetRequestForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                challenge = start_password_reset_verification(form.get_user())
            except PhoneVerificationError as exc:
                form.add_error(None, str(exc))
            else:
                _store_verification_challenge(request, PhoneVerificationChallenge.Purpose.PASSWORD_RESET, challenge)
                return redirect("users:password_reset_request")

    return render(request, "users/password_reset_request.html", {"form": form, "verification": verification})


def password_reset_confirm_view(request):
    return redirect("users:password_reset_request")


@require_POST
def logout_view(request):
    logout(request)
    return redirect(_resolve_next_url(request))


@login_required(login_url="users:login")
def phone_change_request_view(request):
    if not settings.SMS_VERIFICATION_ENABLED:
        _clear_all_verification_sessions(request)
        return redirect("users:profile")

    challenge = _get_verification_challenge(request, PhoneVerificationChallenge.Purpose.PHONE_CHANGE)
    verification = None

    if challenge is not None and challenge.user_id == request.user.pk:
        form = PhoneChangeRequestForm(user=request.user, initial={"phone": challenge.phone})
        verification_form = SmsCodeForm()
        resend_success = False

        if request.method == "POST":
            action = request.POST.get("verification_action")
            if action == "cancel":
                _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.PHONE_CHANGE)
                return redirect("users:phone_change_request")
            if action == "resend":
                challenge, resend_success = _resend_verification_challenge(request, challenge, verification_form)
            elif action == "verify":
                verification_form = SmsCodeForm(request.POST)
                if verification_form.is_valid():
                    try:
                        confirm_phone_change(challenge, verification_form.cleaned_data["code"])
                    except PhoneVerificationError as exc:
                        verification_form.add_error("code", str(exc))
                    else:
                        _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.PHONE_CHANGE)
                        return redirect(f"{reverse('users:profile')}?phone_changed=1")

        verification = _build_code_overlay_context(
            challenge=challenge,
            form=verification_form,
            resend_success=resend_success,
            eyebrow="Зміна номера",
            heading="Підтвердіть новий номер телефону",
            description="Ми надіслали код на новий номер. Після підтвердження він стане основним для входу.",
            submit_label="Оновити номер",
        )
    else:
        if challenge is not None and challenge.user_id != request.user.pk:
            _clear_verification_challenge(request, PhoneVerificationChallenge.Purpose.PHONE_CHANGE)
        form = PhoneChangeRequestForm(request.POST or None, user=request.user)
        if request.method == "POST" and form.is_valid():
            try:
                challenge = start_phone_change_verification(request.user, form.cleaned_data["phone"])
            except PhoneVerificationError as exc:
                form.add_error(None, str(exc))
            else:
                _store_verification_challenge(request, PhoneVerificationChallenge.Purpose.PHONE_CHANGE, challenge)
                return redirect("users:phone_change_request")

    return render(request, "users/phone_change_request.html", {
        "form": form,
        "verification": verification,
        "current_phone_display": format_ua_phone_display(request.user.phone or request.user.username),
    })


@login_required(login_url="users:login")
def phone_change_verify_view(request):
    return redirect("users:phone_change_request")


@login_required(login_url="users:login")
def profile_view(request):
    is_edit_mode = request.GET.get("edit") == "1" or request.method == "POST"
    form = ProfileUpdateForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(f"{reverse('users:profile')}?updated=1")

    orders = list(Order.objects.filter(user=request.user) .prefetch_related("items__product") .order_by("-created_at"))
    for order in orders:
        items = list(order.items.all())
        order.items_count = sum(item.quantity for item in items)
        order.total_amount = sum((item.price_at_order * item.quantity for item in items), Decimal("0"))

    profile_name = " ".join(part for part in [request.user.last_name, request.user.first_name] if part).strip()
    profile_phone_display = format_ua_phone_display(request.user.phone or request.user.username)

    return render(request, "users/profile.html", {
        "orders": orders,
        "form": form,
        "profile_edit_mode": is_edit_mode,
        "profile_updated": request.GET.get("updated") == "1",
        "profile_phone_changed": settings.SMS_VERIFICATION_ENABLED and request.GET.get("phone_changed") == "1",
        "profile_password_reset": settings.SMS_VERIFICATION_ENABLED and request.GET.get("password_reset") == "1",
        "profile_name": profile_name or profile_phone_display,
        "profile_phone_display": profile_phone_display,
        "sms_verification_enabled": settings.SMS_VERIFICATION_ENABLED,
    })


def _clear_all_verification_sessions(request):
    for key in VERIFICATION_SESSION_KEYS.values():
        request.session.pop(key, None)
    request.session.modified = True


def _store_verification_challenge(request, purpose, challenge):
    request.session[VERIFICATION_SESSION_KEYS[purpose]] = challenge.pk
    request.session.modified = True


def _resend_verification_challenge(request, challenge, form):
    try:
        replacement = resend_phone_verification(challenge)
    except PhoneVerificationError as exc:
        form.cleaned_data = {}
        form.add_error(None, str(exc))
        return challenge, False
    _store_verification_challenge(request, replacement.purpose, replacement)
    return replacement, True


def _clear_verification_challenge(request, purpose):
    request.session.pop(VERIFICATION_SESSION_KEYS[purpose], None)
    request.session.modified = True


def _get_verification_challenge(request, purpose):
    challenge_id = request.session.get(VERIFICATION_SESSION_KEYS[purpose])
    if not challenge_id:
        return None
    try:
        return PhoneVerificationChallenge.objects.select_related("user").get(pk=challenge_id, purpose=purpose)
    except PhoneVerificationChallenge.DoesNotExist:
        _clear_verification_challenge(request, purpose)
        return None


def _build_code_overlay_context(*, challenge, form, resend_success, eyebrow, heading, description, submit_label):
    return {
        "form": form,
        "phone_display": format_ua_phone_display(challenge.phone),
        "eyebrow": eyebrow,
        "heading": heading,
        "description": description,
        "submit_label": submit_label,
        "resend_success": resend_success,
        "resend_wait_seconds": get_resend_wait_seconds(challenge),
    }

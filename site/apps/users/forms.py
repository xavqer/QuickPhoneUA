from django import forms
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, password_validation
from django.contrib.auth.forms import UserCreationForm

from apps.forms import apply_required_error_messages

from .phone import normalize_ua_phone
from .services import build_unique_username

INPUT_CLASS = "qp-input w-full rounded-full px-6 py-4 text-sm font-medium placeholder:text-zinc-400/70"


def normalize_sms_code(value):
    digits_only = "".join(ch for ch in value if ch.isdigit())
    if len(digits_only) != settings.SMS_VERIFICATION_CODE_LENGTH:
        raise forms.ValidationError("Введіть коректний код із SMS.")
    return digits_only


def apply_sms_code_widget(field):
    field.widget.attrs.update({
        "class": INPUT_CLASS, "placeholder": "123456", "autocomplete": "one-time-code",
        "inputmode": "numeric", "pattern": "[0-9]*",
    })


class PhoneRegistrationForm(UserCreationForm):
    first_name = forms.CharField(max_length=150, label="Ім'я")
    last_name = forms.CharField(max_length=150, label="Прізвище")
    phone = forms.CharField(max_length=20, label="Номер телефону")

    class Meta:
        model = get_user_model()
        fields = ("first_name", "last_name", "phone", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].label = "Пароль"
        self.fields["password2"].label = "Повторіть пароль"

        self.fields["first_name"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Ім'я", "autocomplete": "given-name"})
        self.fields["last_name"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Прізвище", "autocomplete": "family-name"})
        self.fields["phone"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "+380XXXXXXXXX", "autocomplete": "tel", "inputmode": "tel"}
        )
        self.fields["password1"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "Введіть пароль", "autocomplete": "new-password"}
        )
        self.fields["password2"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "Повторіть пароль", "autocomplete": "new-password"}
        )
        for field in self.fields.values():
            field.help_text = ""
        apply_required_error_messages(self)

    def clean_phone(self):
        normalized = normalize_ua_phone(self.cleaned_data["phone"])
        if self._meta.model.objects.filter(phone=normalized).exists():
            raise forms.ValidationError("Користувач з цим номером уже існує.")
        return normalized

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = build_unique_username(user.phone, user_model=self._meta.model)
        user.phone_verified_at = None
        if commit:
            user.save()
        return user


class PhoneLoginForm(forms.Form):
    phone = forms.CharField(max_length=20, label="Номер телефону")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)

    error_messages = {"invalid_login": "Невірний номер телефону або пароль.", "inactive": "Обліковий запис вимкнено."}

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "+380XXXXXXXXX", "autocomplete": "tel", "inputmode": "tel"}
        )
        self.fields["password"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Ваш пароль", "autocomplete": "current-password"})
        apply_required_error_messages(self)

    def clean_phone(self):
        return normalize_ua_phone(self.cleaned_data["phone"])

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        password = cleaned.get("password")
        if not phone or not password:
            return cleaned

        users = list(get_user_model().objects.filter(phone=phone).order_by("id")[:2])
        if len(users) != 1:
            raise forms.ValidationError(self.error_messages["invalid_login"])
        user = users[0]

        authenticated = authenticate(request=self.request, username=user.get_username(), password=password)
        if authenticated is None:
            raise forms.ValidationError(self.error_messages["invalid_login"])
        if not authenticated.is_active:
            raise forms.ValidationError(self.error_messages["inactive"])

        self.user_cache = authenticated
        return cleaned

    def get_user(self):
        return self.user_cache


class SmsCodeForm(forms.Form):
    code = forms.CharField(max_length=12, label="Код з SMS")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_sms_code_widget(self.fields["code"])
        apply_required_error_messages(self)

    def clean_code(self):
        return normalize_sms_code(self.cleaned_data["code"])


class PasswordResetRequestForm(forms.Form):
    phone = forms.CharField(max_length=20, label="Номер телефону")

    def __init__(self, *args, **kwargs):
        self.user_cache = None
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "+380XXXXXXXXX", "autocomplete": "tel", "inputmode": "tel"}
        )
        apply_required_error_messages(self)

    def clean_phone(self):
        return normalize_ua_phone(self.cleaned_data["phone"])

    def clean(self):
        cleaned = super().clean()
        phone = cleaned.get("phone")
        if not phone:
            return cleaned

        users = list(get_user_model().objects.filter(phone=phone).order_by("id")[:2])
        if len(users) != 1:
            raise forms.ValidationError("Користувача з таким номером не знайдено.")
        if not users[0].is_active:
            raise forms.ValidationError("Обліковий запис вимкнено.")

        self.user_cache = users[0]
        return cleaned

    def get_user(self):
        return self.user_cache


class PasswordResetConfirmForm(forms.Form):
    code = forms.CharField(max_length=12, label="Код з SMS")
    password1 = forms.CharField(label="Новий пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повторіть новий пароль", widget=forms.PasswordInput)

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        apply_sms_code_widget(self.fields["code"])
        self.fields["password1"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Новий пароль", "autocomplete": "new-password"})
        self.fields["password2"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "Повторіть новий пароль", "autocomplete": "new-password"}
        )
        apply_required_error_messages(self)

    def clean_code(self):
        return normalize_sms_code(self.cleaned_data["code"])

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if not password1 or not password2:
            return cleaned
        if password1 != password2:
            self.add_error("password2", "Паролі не збігаються.")
            return cleaned
        try:
            password_validation.validate_password(password1, self.user)
        except forms.ValidationError as exc:
            self.add_error("password1", exc)
        return cleaned


class PhoneChangeRequestForm(forms.Form):
    phone = forms.CharField(max_length=20, label="Новий номер телефону")

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["phone"].widget.attrs.update(
            {"class": INPUT_CLASS, "placeholder": "+380XXXXXXXXX", "autocomplete": "tel", "inputmode": "tel"}
        )
        apply_required_error_messages(self)

    def clean_phone(self):
        normalized = normalize_ua_phone(self.cleaned_data["phone"])
        if self.user and normalized == self.user.phone:
            raise forms.ValidationError("Вкажіть інший номер телефону.")
        users = get_user_model().objects.filter(phone=normalized)
        if self.user:
            users = users.exclude(pk=self.user.pk)
        if users.exists():
            raise forms.ValidationError("Користувач з цим номером уже існує.")
        return normalized


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("last_name", "first_name", "telegram_handle")
        labels = {"last_name": "Прізвище", "first_name": "Ім'я", "telegram_handle": "Telegram"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["last_name"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Прізвище", "autocomplete": "family-name"})
        self.fields["first_name"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "Ім'я", "autocomplete": "given-name"})
        self.fields["telegram_handle"].widget.attrs.update({"class": INPUT_CLASS, "placeholder": "@username", "autocomplete": "off"})
        apply_required_error_messages(self)

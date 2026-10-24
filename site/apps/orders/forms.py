import re

from django import forms

from apps.forms import apply_required_error_messages

from .models import Order

PHONE_DIGITS_RE = re.compile(r"\D+")
TELEGRAM_RE = re.compile(r"^(@[A-Za-z0-9_]{5,32}|\+?\d{10,15})$")


class CheckoutForm(forms.Form):
    delivery_method = forms.ChoiceField(
        choices=Order.DeliveryMethod.choices, required=False, initial=Order.DeliveryMethod.NOVA_POSHTA,
        label="Спосіб отримання", widget=forms.RadioSelect(),
    )
    contact_last_name = forms.CharField(max_length=50, label="Прізвище")
    contact_first_name = forms.CharField(max_length=50, label="Ім'я")
    contact_middle_name = forms.CharField(max_length=50, label="По батькові")
    contact_phone = forms.CharField(max_length=32, label="Телефон")
    contact_telegram = forms.CharField(max_length=120, required=False, label="Telegram (необов'язково)")
    np_city_name = forms.CharField(max_length=200, required=False, label="Місто")
    np_city_ref = forms.CharField(max_length=36, required=False, widget=forms.HiddenInput())
    np_warehouse_name = forms.CharField(max_length=300, required=False, label="Відділення Нової Пошти")
    np_warehouse_ref = forms.CharField(max_length=36, required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in (
            "contact_last_name",
            "contact_first_name",
            "contact_middle_name",
            "contact_phone",
            "contact_telegram",
            "np_city_name",
            "np_warehouse_name",
        ):
            self.fields[name].widget.attrs["class"] = "qp-input liquid-input w-full rounded-full px-6 py-4 text-sm font-medium placeholder:text-zinc-400/70"
        self.fields["contact_phone"].widget.attrs["placeholder"] = "+38 (XXX) XXX XX XX"
        apply_required_error_messages(self)

    def clean_contact_phone(self):
        digits = PHONE_DIGITS_RE.sub("", self.cleaned_data["contact_phone"])
        if len(digits) != 12 or not digits.startswith("380"):
            raise forms.ValidationError("Використайте формат +380XXXXXXXXX.")
        return f"+{digits}"

    def clean_contact_telegram(self):
        value = self.cleaned_data["contact_telegram"]
        if not value:
            return ""
        if not TELEGRAM_RE.match(value):
            raise forms.ValidationError("Вкажіть @username або номер телефону.")
        return value

    def clean(self):
        cleaned = super().clean()
        cleaned["contact_name"] = " ".join(
            cleaned[name] for name in ("contact_last_name", "contact_first_name", "contact_middle_name")
            if cleaned.get(name)
        )
        delivery_method = cleaned.get("delivery_method") or Order.DeliveryMethod.NOVA_POSHTA
        cleaned["delivery_method"] = delivery_method

        if delivery_method == Order.DeliveryMethod.NOVA_POSHTA:
            if not cleaned.get("np_city_name"):
                self.add_error("np_city_name", "Вкажіть місто доставки.")
            if not cleaned.get("np_warehouse_name"):
                self.add_error("np_warehouse_name", "Вкажіть відділення Нової Пошти.")
        else:
            for name in ("np_city_name", "np_city_ref", "np_warehouse_name", "np_warehouse_ref"):
                cleaned[name] = ""
        return cleaned

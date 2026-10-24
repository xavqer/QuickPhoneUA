import re

from django.core.exceptions import ValidationError

UA_PHONE_FORMAT_ERROR = "Вкажіть номер телефону у форматі +380XXXXXXXXX."

NON_DIGIT_RE = re.compile(r"\D+")


def normalize_ua_phone(value):
    raw_value = (value or "").strip()
    digits = NON_DIGIT_RE.sub("", raw_value)
    if len(digits) == 12 and digits.startswith("380"):
        return f"+{digits}"
    elif len(digits) == 10 and digits.startswith("0"):
        return f"+38{digits}"
    raise ValidationError(UA_PHONE_FORMAT_ERROR)


def format_ua_phone_display(value):
    raw_value = (value or "").strip()
    if not raw_value:
        return ""

    digits = NON_DIGIT_RE.sub("", raw_value)
    if len(digits) == 12 and digits.startswith("380"):
        local_digits = digits[2:]
    elif len(digits) == 10 and digits.startswith("0"):
        local_digits = digits
    else:
        return raw_value

    return f"+38 ({local_digits[:3]}) {local_digits[3:6]} {local_digits[6:8]} {local_digits[8:10]}"

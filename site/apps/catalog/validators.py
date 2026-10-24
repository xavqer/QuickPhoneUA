import re

from django.core.exceptions import ValidationError

PRODUCT_PHONE_NUMBER_PLACEHOLDER = "000"
PRODUCT_PHONE_NUMBER_PATTERN = re.compile(r"^\d{3}$")
PRODUCT_PHONE_NUMBER_ERROR_MESSAGE = "Внутрішній номер товару має містити рівно 3 цифри."


def normalize_product_phone_number(value: str | None) -> str:
    cleaned = "".join(str(value or "").split())
    if cleaned == "0":
        return PRODUCT_PHONE_NUMBER_PLACEHOLDER
    return cleaned or PRODUCT_PHONE_NUMBER_PLACEHOLDER


def is_valid_product_phone_number(value: str | None) -> bool:
    return bool(PRODUCT_PHONE_NUMBER_PATTERN.fullmatch(normalize_product_phone_number(value)))


def validate_product_phone_number(value: str | None) -> str:
    cleaned = normalize_product_phone_number(value)
    if not PRODUCT_PHONE_NUMBER_PATTERN.fullmatch(cleaned):
        raise ValidationError(PRODUCT_PHONE_NUMBER_ERROR_MESSAGE)
    return cleaned

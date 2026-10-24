import csv
from collections import defaultdict
from decimal import Decimal, InvalidOperation
from io import StringIO

from django.core.exceptions import ValidationError
from django.db import transaction

from .models import Category, Product, ProductImage
from .validators import normalize_product_phone_number

REQUIRED_PRODUCT_COLUMNS = ("title", "brand", "model_name", "price_uah", "condition_score")
TRUE_VALUES = {"1", "true", "yes", "y", "on", "так", "т", "+"}
FALSE_VALUES = {"0", "false", "no", "n", "off", "ні", "н", "-"}


class ProductBulkImportError(Exception):
    def __init__(self, errors):
        super().__init__("Product bulk import failed.")
        self.errors = errors


def import_products_from_table(
    raw_text,
    *,
    default_category=None, description_template="", default_is_available=True, default_is_active=True,
):
    normalized_text = (raw_text or "").strip()
    if not normalized_text:
        raise ValidationError("Таблиця порожня.")

    fieldnames, rows = _read_rows(normalized_text)
    missing_columns = [column for column in REQUIRED_PRODUCT_COLUMNS if column not in fieldnames]
    if missing_columns:
        raise ValidationError(f"У таблиці бракує обов'язкових колонок: {', '.join(missing_columns)}.")
    if "category" not in fieldnames and default_category is None:
        raise ValidationError("Додайте колонку category або оберіть категорію за замовчуванням.")
    if "description" not in fieldnames and not (description_template or "").strip():
        raise ValidationError("Додайте колонку description або заповніть шаблон опису.")

    category_lookup = _build_category_lookup()
    pending_products = []
    row_errors = []

    for index, row in enumerate(rows, start=2):
        cleaned_row = {key: (value or "").strip() for key, value in row.items() if key}
        if not any(cleaned_row.values()):
            continue
        try:
            category = _resolve_category(cleaned_row.get("category"), default_category, category_lookup)
            price_uah = _parse_decimal(cleaned_row.get("price_uah"), "price_uah")
            condition_score = _parse_decimal(cleaned_row.get("condition_score"), "condition_score")
            battery_health = _parse_optional_int(cleaned_row.get("battery_health"), "battery_health")
            description = cleaned_row.get("description") or _render_description(
                description_template,
                cleaned_row,
                price_uah=price_uah, condition_score=condition_score, battery_health=battery_health,
            )
            product = Product(
                category=category, title=cleaned_row.get("title", ""), brand=cleaned_row.get("brand", ""),
                model_name=cleaned_row.get("model_name", ""),
                phone_number=normalize_product_phone_number(cleaned_row.get("phone_number")), description=description,
                condition_score=condition_score, price_uah=price_uah, battery_health=battery_health,
                is_available=_parse_bool(cleaned_row.get("is_available"), default_is_available, "is_available"),
                is_active=_parse_bool(cleaned_row.get("is_active"), default_is_active, "is_active"),
                show_on_homepage_carousel=_parse_bool(cleaned_row.get("show_on_homepage_carousel"), False, "show_on_homepage_carousel"),
                homepage_carousel_order=_parse_optional_int(
                    cleaned_row.get("homepage_carousel_order"),
                    "homepage_carousel_order",
                    default=0,
                ),
            )
            product.full_clean()
            pending_products.append(product)
        except ValidationError as exc:
            row_errors.append(f"Рядок {index}: {_flatten_validation_error(exc)}")

    if row_errors:
        raise ProductBulkImportError(row_errors)
    if not pending_products:
        raise ValidationError("У таблиці немає жодного валідного рядка для створення товару.")

    with transaction.atomic():
        for product in pending_products:
            product.save()

    return len(pending_products)


def append_product_images(product, uploaded_images):
    images = [image for image in (uploaded_images or []) if image]
    if not images:
        return 0

    has_primary = product.images.filter(is_primary=True).exists()
    last_position = product.images.order_by("-position").values_list("position", flat=True).first() or 0

    with transaction.atomic():
        for offset, image in enumerate(images, start=1):
            ProductImage.objects.create(
                product=product, image=image, alt_text=product.title, is_primary=not has_primary and offset == 1,
                position=last_position + offset,
            )

    return len(images)


def _read_rows(raw_text):
    sample = raw_text[:2048]
    if "\t" in sample:
        delimiter = "\t"
    else:
        try:
            delimiter = csv.Sniffer().sniff(sample, delimiters=",;|").delimiter
        except csv.Error:
            if ";" in sample:
                delimiter = ";"
            elif "," in sample:
                delimiter = ","
            else:
                delimiter = "\t"
    reader = csv.DictReader(StringIO(raw_text), delimiter=delimiter)
    if not reader.fieldnames:
        raise ValidationError("У таблиці немає рядка заголовків.")
    reader.fieldnames = [(name or "").replace("\ufeff", "").strip().lower() for name in reader.fieldnames]
    return reader.fieldnames, list(reader)


def _build_category_lookup():
    lookup = {}
    for category in Category.objects.all():
        lookup[str(category.pk)] = category
        lookup[category.slug.lower()] = category
        lookup[category.name.lower()] = category
    return lookup


def _resolve_category(raw_value, default_category, category_lookup):
    if raw_value:
        key = raw_value.strip().lower()
        if key in category_lookup:
            return category_lookup[key]
        raise ValidationError(f"category: невідома категорія '{raw_value}'.")
    if default_category is not None:
        return default_category
    raise ValidationError("category: категорія не задана.")


def _parse_decimal(value, field_name):
    normalized = (value or "").replace(" ", "").replace("\xa0", "").replace("грн", "").replace("₴", "").strip()
    if normalized.count(",") == 1 and "." not in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        raise ValidationError(f"{field_name}: некоректне число '{value}'.")


def _parse_optional_int(value, field_name, default=None):
    if value in (None, ""):
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        raise ValidationError(f"{field_name}: некоректне ціле число '{value}'.")


def _parse_bool(value, default, field_name):
    if value in (None, ""):
        return default
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValidationError(f"{field_name}: некоректне логічне значення '{value}'.")


def _render_description(template, row, *, price_uah, condition_score, battery_health):
    if not (template or "").strip():
        return ""
    battery_clause = f", акумулятор {battery_health}%" if battery_health is not None else ""
    context = defaultdict(
        str,
        row,
        price_uah=_format_decimal(price_uah), condition_score=_format_decimal(condition_score),
        battery_health="" if battery_health is None else str(battery_health), battery_clause=battery_clause,
    )
    try:
        return template.format_map(context).strip()
    except (ValueError, AttributeError, IndexError, KeyError, TypeError) as exc:
        raise ValidationError(f"Шаблон опису містить помилку: {exc}.")


def _format_decimal(value):
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def _flatten_validation_error(exc):
    if hasattr(exc, "message_dict"):
        parts = []
        for field_name, messages in exc.message_dict.items():
            parts.append(f"{field_name}: {'; '.join(messages)}")
        return " ".join(parts)
    return "; ".join(exc.messages)

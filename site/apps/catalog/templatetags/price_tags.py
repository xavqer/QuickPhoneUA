from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from django import template

register = template.Library()


@register.filter(name="uah")
def uah(value):
    """Format money as '10 000' (no decimals, space as thousands separator)."""
    if value is None or value == "":
        return ""
    try:
        amount = Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return value
    return f"{int(amount):,}".replace(",", " ")


from django.conf import settings
from django.core.cache import cache
from django.db.models import Count

from .models import Category, Product
from .seo import DEFAULT_META_DESCRIPTION, build_absolute_url

_HEADER_CATEGORY_LIMIT = 6
_HEADER_BRAND_LIMIT = 8
_HEADER_MENU_CACHE_KEY = "catalog:header-menu:v1"
_HEADER_MENU_CACHE_TTL = 300


def header_catalog_menu(request):
    cached_menu = cache.get(_HEADER_MENU_CACHE_KEY)
    if cached_menu is not None:
        return cached_menu

    categories = list(Category.objects.filter(is_active=True).order_by("name").values("slug", "name")[:_HEADER_CATEGORY_LIMIT])
    brands = [
        row["brand"]
        for row in (
            Product.objects.filter(is_active=True, is_available=True)
            .exclude(brand="")
            .values("brand")
            .annotate(item_count=Count("id"))
            .order_by("-item_count", "brand")[:_HEADER_BRAND_LIMIT]
        )
    ]

    payload = {"header_nav_categories": categories, "header_nav_brands": brands}
    cache.set(_HEADER_MENU_CACHE_KEY, payload, _HEADER_MENU_CACHE_TTL)
    return payload


def _normalize_telegram_url(value):
    raw = (value or "").strip().strip("\"'")
    if not raw:
        return ""
    if raw.startswith("@"):
        return f"https://t.me/{raw[1:]}"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    return f"https://{raw}"


def site_contact_links(request):
    manager_tg_url = _normalize_telegram_url(settings.CONTACT_MANAGER_TELEGRAM_URL)
    social_tg_url = _normalize_telegram_url(settings.SOCIAL_TELEGRAM_URL)

    return {
        "site_contacts": {
            "phone_display": settings.CONTACT_PHONE_DISPLAY,
            "phone_e164": settings.CONTACT_PHONE_E164,
            "manager_label": settings.CONTACT_MANAGER_LABEL,
            "manager_telegram_url": manager_tg_url,
            "instagram_url": settings.SOCIAL_INSTAGRAM_URL,
            "telegram_url": social_tg_url,
            "tiktok_url": settings.SOCIAL_TIKTOK_URL,
        }
    }


def seo_defaults(request):
    return {"seo_default_canonical_url": build_absolute_url(request), "seo_default_description": DEFAULT_META_DESCRIPTION}

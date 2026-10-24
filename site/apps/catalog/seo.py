from django.conf import settings
from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.utils.text import slugify

from .models import Product

DEFAULT_META_DESCRIPTION = (
    "QuickPhone - магазин вживаних телефонів і смартфонів б/у: iPhone, Samsung "
    "та інші моделі з реальними фото, чесним описом стану та доставкою по Україні."
)


def build_absolute_url(request, path=None):
    target_path = path or request.path
    site_base_url = settings.SITE_BASE_URL.strip().rstrip("/")
    if site_base_url:
        return f"{site_base_url}{target_path}"
    return request.build_absolute_uri(target_path)


class StaticViewSitemap(Sitemap):
    def items(self):
        return ["home", "catalog:list", "privacy_policy"]

    def location(self, item):
        return reverse(item)

    def changefreq(self, item):
        if item == "privacy_policy":
            return "monthly"
        return "daily"

    def priority(self, item):
        if item == "home":
            return 1.0
        if item == "catalog:list":
            return 0.9
        return 0.3


class ProductSitemap(Sitemap):
    changefreq = "daily"
    priority = 0.8

    def items(self):
        return Product.objects.filter(is_active=True, is_available=True).only("id", "title", "updated_at")

    def lastmod(self, obj):
        return obj.updated_at

    def location(self, obj):
        slug = slugify(obj.title) or f"product-{obj.pk}"
        return reverse("catalog:product_detail", kwargs={"pk": obj.pk, "slug": slug})


sitemaps = {"static": StaticViewSitemap, "products": ProductSitemap}


def robots_txt(request):
    lines = [
        "User-agent: *",
        "Allow: /",
        "Disallow: /upravlinnia-mahazynom/",
        "",
        f"Sitemap: {build_absolute_url(request, reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")

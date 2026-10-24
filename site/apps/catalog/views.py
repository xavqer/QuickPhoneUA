from decimal import Decimal, InvalidOperation

from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.aggregates import Max, Min
from django.shortcuts import get_object_or_404, redirect, render
from django.template.response import TemplateResponse
from django.urls import reverse
from django.utils.text import slugify

from .forms import CatalogFilterForm
from .models import Category, DeviceModel, Product

DEFAULT_SORT = "date_desc"
HOME_CAROUSEL_LIMIT = 8
SORT_ORDERING = {"date_desc": "-created_at", "date_asc": "created_at", "price_asc": "price_uah", "price_desc": "-price_uah"}


def home_page(request):
    base_queryset = Product.objects.filter(is_active=True, is_available=True).select_related("category").prefetch_related("images")
    home_carousel_products = list(
        base_queryset.filter(show_on_homepage_carousel=True)
        .order_by("homepage_carousel_order", "-created_at", "-id")[:HOME_CAROUSEL_LIMIT]
    )
    if not home_carousel_products:
        home_carousel_products = list(base_queryset.order_by("-created_at", "-id")[:HOME_CAROUSEL_LIMIT])
    return render(request, "home.html", {
        "home_carousel_products": home_carousel_products, "home_carousel_count": len(home_carousel_products),
    })


def privacy_policy_page(request):
    return render(request, "privacy_policy.html")


def _build_choices():
    categories = list(Category.objects.filter(is_active=True).values_list("slug", "name"))
    brands = [
        (brand, brand)
        for brand in Product.objects.filter(is_active=True)
        .order_by("brand")
        .values_list("brand", flat=True)
        .distinct()
        if brand
    ]
    return categories, brands


def _parse_price_param(value, fallback):
    if value in ("", None):
        return fallback
    try:
        price = Decimal(value)
        if not price.is_finite() or price.copy_abs() > Decimal("99999999.99"):
            return fallback
        return int(price)
    except (InvalidOperation, TypeError, ValueError):
        return fallback


def _build_remove_url(request_path, query_dict, key, value=None):
    remove_query = query_dict.copy()
    if value is None:
        remove_query.pop(key, None)
    else:
        remaining_values = [item for item in remove_query.getlist(key) if item != value]
        remove_query.pop(key, None)
        for item in remaining_values:
            remove_query.appendlist(key, item)
    return f"{request_path}?{remove_query.urlencode()}" if remove_query else request_path


def _build_active_filters(path, query_dict, category_names):
    sort_labels = dict(CatalogFilterForm.SORT_CHOICES)
    labels = {
        "q": f"Пошук: {query_dict.get('q')}",
        "category": category_names.get(query_dict.get("category"), query_dict.get("category")),
        "brand": None,
        "min_price": f"Мін: {query_dict.get('min_price')} грн",
        "max_price": f"Макс: {query_dict.get('max_price')} грн",
        "condition": f"Стан >= {query_dict.get('condition')}",
        "sort": sort_labels.get(query_dict.get("sort"), query_dict.get("sort")),
    }
    active_filters = []
    for key, label in labels.items():
        if key == "sort" and query_dict.get(key) == DEFAULT_SORT:
            continue
        values = query_dict.getlist(key) if key == "brand" else [query_dict.get(key)]
        for value in values:
            if value:
                active_filters.append({
                    "key": key,
                    "label": value if key == "brand" else label,
                    "remove_url": _build_remove_url(path, query_dict, key, value if key == "brand" else None),
                })
    return active_filters


def catalog_list(request):
    categories, brands = _build_choices()
    category_name_by_slug = {slug: name for slug, name in categories}
    base_queryset = Product.objects.filter(is_active=True)
    price_stats = base_queryset.aggregate(min_price=Min("price_uah"), max_price=Max("price_uah"))
    price_floor = int(price_stats["min_price"] or 0)
    price_ceiling = int(price_stats["max_price"] or 0)

    form = CatalogFilterForm(request.GET or None, categories=categories, brands=brands)
    queryset = base_queryset.select_related("category").prefetch_related("images")
    selected_category = ""
    selected_brands = []
    selected_sort = DEFAULT_SORT
    selected_min_price = price_floor
    selected_max_price = price_ceiling
    search_query = (request.GET.get("q") or "").strip()

    if form.is_valid():
        data = form.cleaned_data
        selected_category = data["category"]
        selected_brands = data["brand"]
        selected_sort = data["sort"] or DEFAULT_SORT
        search_query = data["q"]

        if data["min_price"] is not None:
            selected_min_price = int(data["min_price"])
        if data["max_price"] is not None:
            selected_max_price = int(data["max_price"])

        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query)
                | Q(brand__icontains=search_query)
                | Q(model_name__icontains=search_query)
                | Q(description__icontains=search_query)
            )
        if selected_category:
            queryset = queryset.filter(category__slug=selected_category)
        if selected_brands:
            queryset = queryset.filter(brand__in=selected_brands)
        if data["min_price"] is not None:
            queryset = queryset.filter(price_uah__gte=data["min_price"])
        if data["max_price"] is not None:
            queryset = queryset.filter(price_uah__lte=data["max_price"])
        if data["condition"]:
            queryset = queryset.filter(condition_score__gte=data["condition"])
    else:
        selected_category = request.GET.get("category", "")
        selected_brands = [brand for brand in request.GET.getlist("brand") if brand]
        selected_sort = request.GET.get("sort") or DEFAULT_SORT
        selected_min_price = _parse_price_param(request.GET.get("min_price"), price_floor)
        selected_max_price = _parse_price_param(request.GET.get("max_price"), price_ceiling)

    if selected_min_price > selected_max_price:
        selected_min_price, selected_max_price = selected_max_price, selected_min_price

    queryset = queryset.order_by(SORT_ORDERING.get(selected_sort, SORT_ORDERING[DEFAULT_SORT]), "-id")

    paginator = Paginator(queryset, 12)
    page_obj = paginator.get_page(request.GET.get("page"))

    query_dict = request.GET.copy()
    query_dict.pop("page", None)

    active_filters = _build_active_filters(request.path, query_dict, category_name_by_slug)

    context = {
        "form": form,
        "page_obj": page_obj,
        "products": page_obj.object_list,
        "total_count": paginator.count,
        "base_query": query_dict.urlencode(),
        "filters_applied": bool(active_filters),
        "active_filters": active_filters,
        "current_category_name": category_name_by_slug.get(selected_category, "Всі вживані телефони"),
        "category_options": categories,
        "brand_options": [brand for brand, _ in brands],
        "selected_category": selected_category,
        "selected_brands": selected_brands,
        "price_floor": price_floor,
        "price_ceiling": price_ceiling,
        "selected_min_price": selected_min_price,
        "selected_max_price": selected_max_price,
        "sort_choices": CatalogFilterForm.SORT_CHOICES,
        "selected_sort": selected_sort if selected_sort in SORT_ORDERING else DEFAULT_SORT,
        "search_query": search_query,
    }

    if request.htmx:
        return TemplateResponse(request, "catalog/partials/result_grid.html", context)
    return render(request, "catalog/catalog_page.html", context)


def product_detail(request, pk, slug):
    product = get_object_or_404(Product.objects.filter(is_active=True).select_related("category").prefetch_related("images"), pk=pk)

    canonical_slug = slugify(product.title) or f"product-{product.pk}"
    if slug != canonical_slug:
        return redirect("catalog:product_detail", pk=product.pk, slug=canonical_slug, permanent=True)

    images = list(product.images.all())
    primary_image = next((img for img in images if img.is_primary), images[0] if images else None)
    device_model = (
        DeviceModel.objects.filter(brand__iexact=product.brand, name__iexact=product.model_name)
        .prefetch_related("specs")
        .first()
    )
    model_specs = list(device_model.specs.all()) if device_model else []

    return render(request, "catalog/product_detail.html",
        {"product": product, "images": images, "primary_image": primary_image, "model_specs": model_specs},
    )


def search_suggestions(request):
    term = (request.GET.get("q") or "").strip()
    if len(term) < 2:
        return JsonResponse({"items": []})

    matches = (
        Product.objects.filter(is_active=True, is_available=True)
.filter(Q(title__icontains=term) | Q(brand__icontains=term) | Q(model_name__icontains=term) | Q(description__icontains=term))
        .only("id", "title", "brand", "model_name", "price_uah", "created_at")
        .order_by("-created_at", "-id")[:5]
    )

    items = []
    for product in matches:
        product_slug = slugify(product.title) or f"product-{product.pk}"
        subtitle = " ".join(part for part in [product.brand, product.model_name] if part)
        items.append(
            {
                "id": product.pk,
                "title": product.title,
                "subtitle": subtitle,
                "price_uah": int(product.price_uah),
                "url": reverse("catalog:product_detail", kwargs={"pk": product.pk, "slug": product_slug}),
            }
        )

    return JsonResponse({"items": items})

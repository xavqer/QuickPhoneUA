from urllib.parse import urlencode
from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from apps.catalog.models import Product
from apps.users.phone import format_ua_phone_display

from .cart import SessionCart
from .forms import CheckoutForm
from .models import Order, OrderItem
from .np_service import NovaPoshtaService


def _parse_product_id(value):
    try:
        product_id = int(value)
    except (TypeError, ValueError):
        return None
    return product_id if 0 < product_id <= 2**63 - 1 else None


def _cart_total(products):
    return sum((product.price_uah for product in products), Decimal("0.00"))


def _commission_amount(product_total, delivery_method=Order.DeliveryMethod.NOVA_POSHTA):
    if delivery_method == Order.DeliveryMethod.PICKUP or product_total <= 0:
        return Decimal("0.00")
    commission = product_total * Decimal("0.02") + Decimal("20")
    return commission.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _checkout_total_with_fees(product_total, delivery_method=Order.DeliveryMethod.NOVA_POSHTA, delivery_estimate_max=None):
    total = product_total + _commission_amount(product_total, delivery_method)
    if delivery_method != Order.DeliveryMethod.PICKUP and delivery_estimate_max is not None:
        total += delivery_estimate_max
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _cart_context(cart, delivery_method=Order.DeliveryMethod.NOVA_POSHTA):
    products = cart.products()
    cart_total = _cart_total(products)
    return {
        "cart_products": products,
        "cart_count": cart.count(),
        "cart_total": cart_total,
        "commission_fee": _commission_amount(cart_total, delivery_method),
        "checkout_total": _checkout_total_with_fees(cart_total, delivery_method),
    }


def _guest_registration_after_checkout_url(request, order):
    if request.user.is_authenticated:
        return ""

    parts = (order.contact_name or "").split()
    last_name = parts[0] if parts else ""
    first_name = parts[1] if len(parts) > 1 else ""
    query = {"last_name": last_name, "first_name": first_name, "next": reverse("users:profile")}
    return f"{reverse('users:register')}?{urlencode(query)}"


def _checkout_form_with_initial(user, post_data=None):
    if post_data and any(field_name in post_data for field_name in CheckoutForm.base_fields):
        return CheckoutForm(initial={name: post_data.get(name, "") for name in CheckoutForm.base_fields})

    initial = {}
    if user.is_authenticated:
        initial = {
            "delivery_method": Order.DeliveryMethod.NOVA_POSHTA,
            "contact_last_name": user.last_name.strip(),
            "contact_first_name": user.first_name.strip(),
            "contact_middle_name": "",
            "contact_phone": format_ua_phone_display(user.phone or user.username),
            "contact_telegram": user.telegram_handle.strip(),
        }
    return CheckoutForm(initial=initial)


def _render_cart_updates(request, message="", level="info", status=200):
    return render(request, "orders/partials/cart_update_response.html",
        {"message": message, "level": level, **_cart_context(SessionCart(request))},
        status=status,
    )


@require_GET
def cart_badge(request):
    cart = SessionCart(request)
    return render(request, "orders/partials/cart_badge.html", {"cart_count": cart.count()})


@require_GET
def cart_panel(request):
    cart = SessionCart(request)
    return render(request, "orders/partials/cart_panel.html", _cart_context(cart))


@require_POST
def cart_add(request):
    product_id = _parse_product_id(request.POST.get("product_id"))
    if product_id is None:
        return HttpResponseBadRequest("Missing or invalid product_id")
    product = Product.objects.filter(id=product_id).first()
    if not product:
        return _render_cart_updates(request, "Товар не знайдено.", "error", status=404)

    cart = SessionCart(request)
    ok, message, level = cart.add(product)
    return _render_cart_updates(request, message, level, status=200 if ok else 409)


@require_POST
def buy_now(request):
    product_id = _parse_product_id(request.POST.get("product_id"))
    if product_id is None:
        return HttpResponseBadRequest("Missing or invalid product_id")

    product = Product.objects.filter(id=product_id).first()
    if not product:
        return redirect("catalog:list")

    cart = SessionCart(request)
    ok, _, _ = cart.add(product)
    if ok:
        return redirect("orders:checkout")

    return redirect("catalog:product_detail", pk=product.pk, slug=slugify(product.title))


@require_POST
def cart_remove(request):
    product_id = _parse_product_id(request.POST.get("product_id"))
    if product_id is None:
        return HttpResponseBadRequest("Missing or invalid product_id")
    cart = SessionCart(request)
    cart.remove(product_id)
    return _render_cart_updates(request, "Товар видалено з кошика.", "success")


@require_GET
def np_city_search(request):
    query = request.GET.get("q") or request.GET.get("np_city_name", "")
    service = NovaPoshtaService()
    result = service.search_cities(query)
    return render(request, "orders/partials/np_city_results.html",
        {"cities": result["data"], "query": query, "error_type": result.get("error_type"), "message": result.get("message", "")},
    )


@require_GET
def np_warehouses(request):
    city_ref = request.GET.get("city_ref", "")
    service = NovaPoshtaService()
    result = service.get_warehouses(city_ref)
    return render(request, "orders/partials/np_warehouse_options.html",
        {"city_ref": city_ref, "warehouses": result["data"], "error_type": result.get("error_type"), "message": result.get("message", "")},
    )


@require_GET
def np_estimate(request):
    cart_total = _cart_total(SessionCart(request).products())
    commission_fee = _commission_amount(cart_total, Order.DeliveryMethod.NOVA_POSHTA)
    checkout_total_base = _checkout_total_with_fees(cart_total, Order.DeliveryMethod.NOVA_POSHTA)
    service = NovaPoshtaService()
    result = service.estimate_delivery_range(
        request.GET.get("city_ref", ""),
        request.GET.get("warehouse_ref", ""),
            declared_cost_uah=cart_total,
    )
    estimate = result["data"] if result["ok"] else None
    return render(request, "orders/partials/np_estimate_hidden.html",
        {
            "estimate_min": estimate["min"] if estimate else "",
            "estimate_max": estimate["max"] if estimate else "",
            "estimate_message": "" if result["ok"] else result.get("message", ""),
            "cart_total": cart_total,
            "commission_fee": commission_fee,
            "checkout_total": _checkout_total_with_fees(cart_total, delivery_estimate_max=estimate["max"] if estimate else None),
            "checkout_total_base": checkout_total_base,
            "emit_oob": True,
        },
    )


@require_GET
@ensure_csrf_cookie
def checkout_page(request):
    cart = SessionCart(request)
    cart_context = _cart_context(cart)
    return render(request, "orders/checkout_page.html", {"form": _checkout_form_with_initial(user=request.user), **cart_context})


@require_POST
def checkout_remove(request):
    product_id = _parse_product_id(request.POST.get("product_id"))
    if product_id is None:
        return HttpResponseBadRequest("Missing or invalid product_id")

    cart = SessionCart(request)
    cart.remove(product_id)
    selected_delivery_method = request.POST.get("delivery_method", "").strip()
    cart_context = _cart_context(cart, selected_delivery_method)

    return render(request, "orders/partials/cart_update_response.html",
        {"form": _checkout_form_with_initial(request.user, request.POST), **cart_context},
    )


@require_POST
def checkout_submit(request):
    cart = SessionCart(request)
    products = cart.products()
    cart_total = _cart_total(products)
    selected_delivery_method = request.POST.get("delivery_method", "").strip()
    form = CheckoutForm(request.POST)
    error = None
    error_status = 400
    if not products:
        error = "Кошик порожній."
    elif not form.is_valid():
        error = "Будь ласка, виправте помилки нижче."
    elif any(not product.is_available or not product.is_active for product in products):
        error = "Один або кілька товарів стали недоступними."
        error_status = 409

    if error:
        return render(request, "orders/partials/checkout_form.html",
            {
                "form": form,
                "cart_products": products,
                "cart_count": cart.count() if products else 0,
                "cart_total": cart_total if products else 0,
                "commission_fee": _commission_amount(cart_total, selected_delivery_method),
                "checkout_total": _checkout_total_with_fees(cart_total, selected_delivery_method),
                "top_error": error,
            },
            status=error_status,
        )

    delivery_method = form.cleaned_data["delivery_method"]
    estimate_range = None
    if delivery_method == Order.DeliveryMethod.NOVA_POSHTA:
        service = NovaPoshtaService()
        estimate_result = service.estimate_delivery_range(
            form.cleaned_data["np_city_ref"],
            form.cleaned_data["np_warehouse_ref"],
            declared_cost_uah=cart_total,
        )
        estimate_range = estimate_result["data"] if estimate_result.get("ok") else None
    commission_fee = _commission_amount(cart_total, delivery_method)
    checkout_total = _checkout_total_with_fees(cart_total, delivery_method, estimate_range["max"] if estimate_range else None)

    with transaction.atomic():
        order = Order.objects.create(
            user=request.user if request.user.is_authenticated else None,
            contact_name=form.cleaned_data["contact_name"], contact_phone=form.cleaned_data["contact_phone"],
            contact_telegram=form.cleaned_data["contact_telegram"], delivery_method=delivery_method,
            np_city_name=form.cleaned_data["np_city_name"], np_city_ref=form.cleaned_data["np_city_ref"],
            np_warehouse_name=form.cleaned_data["np_warehouse_name"],
            np_warehouse_ref=form.cleaned_data["np_warehouse_ref"],
            delivery_cost_estimate=estimate_range["max"] if estimate_range else None,
        )

        OrderItem.objects.bulk_create(
            [OrderItem(order=order, product=product, quantity=1, price_at_order=product.price_uah) for product in products]
        )

    cart.clear()
    return render(request, "orders/partials/checkout_success.html",
        {
            "order": order,
            "estimate_range": estimate_range,
            "cart_total": cart_total,
            "commission_fee": commission_fee,
            "checkout_total": checkout_total,
            "register_after_checkout_url": _guest_registration_after_checkout_url(request, order),
        },
    )


from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "quantity", "price_at_order")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "created_at",
        "delivery_method",
        "contact_name",
        "contact_phone",
        "contact_telegram",
        "np_city_name",
        "np_warehouse_name",
        "status",
    )
    list_filter = ("delivery_method", "status", "created_at")
    search_fields = ("id", "contact_name", "contact_phone", "contact_telegram", "np_city_name", "np_warehouse_name")
    list_editable = ("status",)
    ordering = ("-created_at",)
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "product", "quantity", "price_at_order")
    search_fields = ("order__id", "product__title")

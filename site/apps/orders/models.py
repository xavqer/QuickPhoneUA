from django.conf import settings
from django.db import models

from apps.catalog.models import Product


class Order(models.Model):
    class DeliveryMethod(models.TextChoices):
        NOVA_POSHTA = "nova_poshta", "Nova Poshta"
        PICKUP = "pickup", "Pickup"

    class Status(models.TextChoices):
        PENDING_REVIEW = "pending_review", "Pending review"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="orders")
    contact_name = models.CharField(max_length=160)
    contact_phone = models.CharField(max_length=24)
    contact_telegram = models.CharField(max_length=120, blank=True)
    delivery_method = models.CharField(max_length=20, choices=DeliveryMethod.choices, default=DeliveryMethod.NOVA_POSHTA)
    np_city_name = models.CharField(max_length=200, blank=True)
    np_city_ref = models.CharField(max_length=36, blank=True)
    np_warehouse_name = models.CharField(max_length=300, blank=True)
    np_warehouse_ref = models.CharField(max_length=36, blank=True)
    delivery_cost_estimate = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING_REVIEW)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def get_status_display_uk(self):
        labels = {
            self.Status.PENDING_REVIEW: "Очікує підтвердження",
            self.Status.CONFIRMED: "Підтверджено",
            self.Status.SHIPPED: "Відправлено",
            self.Status.DELIVERED: "Доставлено",
            self.Status.CANCELLED: "Скасовано",
        }
        return labels.get(self.status, self.get_status_display())

    def get_delivery_method_display_uk(self):
        labels = {self.DeliveryMethod.NOVA_POSHTA: "Нова Пошта", self.DeliveryMethod.PICKUP: "Самовивіз"}
        return labels.get(self.delivery_method, self.get_delivery_method_display())

    def __str__(self):
        return f"Order #{self.id}"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField(default=1)
    price_at_order = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.title} x{self.quantity}"

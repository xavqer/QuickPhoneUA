from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Q

from .validators import (
    PRODUCT_PHONE_NUMBER_ERROR_MESSAGE,
    PRODUCT_PHONE_NUMBER_PLACEHOLDER,
    is_valid_product_phone_number,
    normalize_product_phone_number,
)


class Category(models.Model):
    name = models.CharField(max_length=120, unique=True)
    slug = models.SlugField(max_length=140, unique=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    title = models.CharField(max_length=200)
    brand = models.CharField(max_length=100)
    model_name = models.CharField(max_length=120)
    phone_number = models.CharField(max_length=32, default=PRODUCT_PHONE_NUMBER_PLACEHOLDER)
    description = models.TextField()
    condition_score = models.DecimalField(max_digits=3, decimal_places=1, validators=[MinValueValidator(0.0), MaxValueValidator(10.0)])
    price_uah = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    show_on_homepage_carousel = models.BooleanField(default=False, help_text="Показувати товар у carousel на головній сторінці.")
    homepage_carousel_order = models.PositiveSmallIntegerField(
        default=0, help_text="Менше число показується раніше у carousel на головній сторінці.",
    )
    battery_health = models.PositiveSmallIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(100)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(condition_score__gte=0) & Q(condition_score__lte=10), name="product_condition_0_10"),
            models.CheckConstraint(condition=Q(price_uah__gte=0), name="product_price_non_negative"),
        ]
        indexes = [
            models.Index(fields=["is_active", "is_available"]),
            models.Index(fields=["show_on_homepage_carousel", "homepage_carousel_order"], name="catalog_home_carousel_idx"),
            models.Index(fields=["brand", "model_name"]),
            models.Index(fields=["price_uah"]),
        ]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        normalized_phone_number = normalize_product_phone_number(self.phone_number)
        if is_valid_product_phone_number(normalized_phone_number):
            self.phone_number = normalized_phone_number
            return

        # Replace unchanged legacy contact numbers with the stock placeholder.
        if self.pk:
            original_phone_number = type(self)._default_manager.filter(pk=self.pk).values_list("phone_number", flat=True).first()
            if original_phone_number == self.phone_number and not is_valid_product_phone_number(original_phone_number):
                self.phone_number = PRODUCT_PHONE_NUMBER_PLACEHOLDER
                return

        raise ValidationError({"phone_number": [PRODUCT_PHONE_NUMBER_ERROR_MESSAGE]})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/%Y/%m/")
    alt_text = models.CharField(max_length=180, blank=True)
    is_primary = models.BooleanField(default=False)
    position = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["product"], condition=Q(is_primary=True), name="single_primary_image_per_product")]

    def __str__(self):
        return f"{self.product.title} image #{self.id}"


class DeviceModel(models.Model):
    brand = models.CharField(max_length=100)
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["brand", "name"]
        constraints = [models.UniqueConstraint(fields=["brand", "name"], name="unique_device_model_brand_name")]
        indexes = [models.Index(fields=["brand", "name"])]

    def __str__(self):
        return f"{self.brand} {self.name}".strip()


class DeviceModelSpec(models.Model):
    device_model = models.ForeignKey(DeviceModel, on_delete=models.CASCADE, related_name="specs")
    label = models.CharField(max_length=120)
    value = models.CharField(max_length=240)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [models.UniqueConstraint(fields=["device_model", "label"], name="unique_device_model_spec_label")]

    def __str__(self):
        return f"{self.device_model}: {self.label}"

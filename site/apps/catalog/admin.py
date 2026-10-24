from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from .admin_forms import ProductAdminForm, ProductBulkImportForm
from .models import Category, DeviceModel, DeviceModelSpec, Product, ProductImage
from .services import ProductBulkImportError, append_product_images, import_products_from_table


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("image", "alt_text", "is_primary", "position")
    ordering = ("position",)


class DeviceModelSpecInline(admin.TabularInline):
    model = DeviceModelSpec
    extra = 1
    fields = ("label", "value", "position")
    ordering = ("position", "id")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    form = ProductAdminForm
    change_list_template = "admin/catalog/product/change_list.html"
    list_display = (
        "title",
        "category",
        "brand",
        "model_name",
        "phone_number",
        "condition_score",
        "price_uah",
        "show_on_homepage_carousel",
        "homepage_carousel_order",
        "is_available",
        "is_active",
    )
    list_filter = ("show_on_homepage_carousel", "is_active", "is_available", "category", "brand")
    search_fields = ("title", "brand", "model_name", "phone_number", "description")
    list_editable = ("show_on_homepage_carousel", "homepage_carousel_order", "is_available", "is_active")
    inlines = [ProductImageInline]
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "category",
                    "title",
                    "brand",
                    "model_name",
                    "phone_number",
                    "description",
                    "condition_score",
                    "price_uah",
                    "battery_health",
                    "additional_images",
                )
            },
        ),
        ("Видимість та головна", {"fields": ("is_available", "is_active", "show_on_homepage_carousel", "homepage_carousel_order")}),
    )

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [path("bulk-import/", self.admin_site.admin_view(self.bulk_import_view), name="catalog_product_bulk_import")]
        return custom_urls + urls

    def bulk_import_view(self, request):
        if not self.has_add_permission(request):
            raise PermissionDenied

        form = ProductBulkImportForm(request.POST or None, request.FILES or None)
        import_errors = []
        if request.method == "POST" and form.is_valid():
            try:
                created_count = import_products_from_table(
                    form.get_source_text(),
                    default_category=form.cleaned_data["default_category"],
                    description_template=form.cleaned_data["description_template"],
                    default_is_available=form.cleaned_data["default_is_available"],
                    default_is_active=form.cleaned_data["default_is_active"],
                )
            except ValidationError as exc:
                form.add_error(None, exc)
            except ProductBulkImportError as exc:
                import_errors = exc.errors
            else:
                self.message_user(request, f"Створено товарів: {created_count}.", level=messages.SUCCESS)
                changelist_url = reverse("admin:catalog_product_changelist")
                return HttpResponseRedirect(changelist_url)

        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "form": form,
            "import_errors": import_errors,
            "media": self.media + form.media,
            "title": "Масове додавання товарів",
        }
        return TemplateResponse(request, "admin/catalog/product/bulk_import.html", context)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        created_count = append_product_images(form.instance, form.cleaned_data["additional_images"])
        if created_count:
            self.message_user(request, f"Додано фото: {created_count}.", level=messages.SUCCESS)


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("id", "product", "is_primary", "position", "created_at")
    list_filter = ("is_primary",)
    search_fields = ("product__title", "alt_text")


@admin.register(DeviceModel)
class DeviceModelAdmin(admin.ModelAdmin):
    list_display = ("brand", "name", "updated_at")
    search_fields = ("brand", "name")
    inlines = [DeviceModelSpecInline]

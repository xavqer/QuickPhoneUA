from django import forms

from .models import Category, Product
from .validators import PRODUCT_PHONE_NUMBER_PLACEHOLDER, validate_product_phone_number

DEFAULT_PRODUCT_DESCRIPTION_TEMPLATE = (
    "{title} у перевіреному стані. "
    "Смартфон {brand} {model_name} з оцінкою стану {condition_score}/10"
    "{battery_clause}. Актуальна ціна: {price_uah} грн."
)


class MultipleImageFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if hasattr(files, "getlist"):
            return files.getlist(name)
        return super().value_from_datadict(data, files, name)


class MultipleImageField(forms.ImageField):
    widget = MultipleImageFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if not isinstance(data, (list, tuple)):
            data = [data]
        parent_clean = super().clean
        return [parent_clean(item, initial) for item in data]


class ProductAdminForm(forms.ModelForm):
    phone_number = forms.CharField(
        required=False, max_length=3, initial=PRODUCT_PHONE_NUMBER_PLACEHOLDER, label="Внутрішній номер",
        help_text="Рівно 3 цифри. Значення 000 означає, що номер ще не призначено.",
    )
    additional_images = MultipleImageField(
        label="Додати кілька фото", required=False,
        help_text="Можна вибрати одразу кілька зображень. Вони додадуться після збереження товару.",
    )

    class Meta:
        model = Product
        fields = "__all__"

    def clean_phone_number(self):
        return validate_product_phone_number(self.cleaned_data["phone_number"])


class ProductBulkImportForm(forms.Form):
    source_text = forms.CharField(
        label="Таблиця товарів", required=False,
        widget=forms.Textarea(attrs={"rows": 18, "cols": 120, "class": "vLargeTextField"}),
        help_text="Вставте таблицю з Excel або Google Sheets чи CSV/TSV з заголовком колонок.",
    )
    source_file = forms.FileField(
        label="CSV або TSV файл", required=False,
        help_text="Підтримуються UTF-8 і Windows-1251 файли. Поле можна лишити порожнім, якщо таблиця вставлена вище.",
    )
    default_category = forms.ModelChoiceField(
        label="Категорія за замовчуванням", queryset=Category.objects.order_by("name"), required=False,
        help_text="Використовується, якщо у таблиці немає колонки category.",
    )
    description_template = forms.CharField(
        label="Шаблон опису", required=False, initial=DEFAULT_PRODUCT_DESCRIPTION_TEMPLATE,
        widget=forms.Textarea(attrs={"rows": 5, "class": "vLargeTextField"}), help_text=(
            "Підставляється, якщо в таблиці немає колонки description. "
            "Доступні змінні: {title}, {brand}, {model_name}, {price_uah}, "
            "{condition_score}, {battery_health}, {battery_clause}."
        ),
    )
    default_is_available = forms.BooleanField(label="Товари в наявності за замовчуванням", required=False, initial=True)
    default_is_active = forms.BooleanField(label="Товари активні за замовчуванням", required=False, initial=True)

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("source_text") and not cleaned_data.get("source_file"):
            raise forms.ValidationError("Додайте таблицю у текстове поле або завантажте CSV/TSV файл.")
        return cleaned_data

    def get_source_text(self):
        uploaded_file = self.cleaned_data["source_file"]
        if uploaded_file:
            raw_bytes = uploaded_file.read()
            for encoding in ("utf-8-sig", "cp1251"):
                try:
                    return raw_bytes.decode(encoding)
                except UnicodeDecodeError:
                    continue
            raise forms.ValidationError("Не вдалося прочитати файл. Збережіть його у UTF-8 або Windows-1251.")
        return self.cleaned_data["source_text"]

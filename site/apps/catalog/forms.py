from decimal import Decimal

from django import forms


class CatalogFilterForm(forms.Form):
    SORT_CHOICES = (
        ("date_desc", "Спочатку нові"),
        ("date_asc", "Спочатку старіші"),
        ("price_asc", "Ціна: від дешевих"),
        ("price_desc", "Ціна: від дорогих"),
    )

    q = forms.CharField(required=False, max_length=120)
    category = forms.ChoiceField(required=False)
    brand = forms.MultipleChoiceField(required=False)
    min_price = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    max_price = forms.DecimalField(required=False, min_value=Decimal("0"), max_digits=10, decimal_places=2)
    sort = forms.ChoiceField(required=False, choices=SORT_CHOICES)
    condition = forms.ChoiceField(
        required=False, choices=[("", "Будь-який стан"), ("9", "9.0+"), ("8", "8.0+"), ("7", "7.0+"), ("6", "6.0+")],
    )

    def __init__(self, *args, categories=None, brands=None, **kwargs):
        super().__init__(*args, **kwargs)
        category_choices = [("", "Усі категорії")]
        brand_choices = [("", "Усі бренди")]
        if categories:
            category_choices.extend(categories)
        if brands:
            brand_choices.extend(brands)
        self.fields["category"].choices = category_choices
        self.fields["brand"].choices = brand_choices
        self.fields["sort"].choices = self.SORT_CHOICES

    def clean(self):
        cleaned_data = super().clean()
        min_price = cleaned_data.get("min_price")
        max_price = cleaned_data.get("max_price")
        if min_price is not None and max_price is not None and min_price > max_price:
            self.add_error("max_price", "Максимальна ціна має бути більшою або дорівнювати мінімальній.")
        return cleaned_data

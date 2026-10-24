from __future__ import annotations

from apps.catalog.models import Product

SESSION_KEY = "cart_product_ids"


class SessionCart:
    def __init__(self, request):
        self.session = request.session

    def _product_ids(self) -> list[int]:
        return [int(value) for value in self.session.get(SESSION_KEY, [])]

    def _save_product_ids(self, product_ids: list[int]):
        self.session[SESSION_KEY] = product_ids
        self.session.modified = True

    def add(self, product: Product) -> tuple[bool, str, str]:
        if not product.is_active or not product.is_available:
            return False, "Цей товар недоступний.", "error"
        product_ids = self._product_ids()
        if product.id not in product_ids:
            product_ids.append(product.id)
            self._save_product_ids(product_ids)
            return True, "Товар додано до кошика.", "success"
        return True, "Товар уже є у вашому кошику.", "info"

    def remove(self, product_id: int):
        product_ids = self._product_ids()
        if product_id in product_ids:
            product_ids.remove(product_id)
            self._save_product_ids(product_ids)

    def clear(self):
        self._save_product_ids([])

    def count(self) -> int:
        return len(self._product_ids())

    def products(self):
        product_ids = self._product_ids()
        if not product_ids:
            return []
        products_by_id = {
            product.id: product
            for product in Product.objects.filter(id__in=product_ids).select_related("category").prefetch_related("images")
        }
        return [products_by_id[product_id] for product_id in product_ids if product_id in products_by_id]

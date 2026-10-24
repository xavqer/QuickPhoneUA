import json
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from urllib.error import URLError
from urllib.request import Request, urlopen


class NovaPoshtaClient:
    base_url = "https://api.novaposhta.ua/v2.0/json/"

    def __init__(self, api_key=None, timeout=None):
        self.api_key = api_key or os.getenv("NP_API_KEY", "")
        self.timeout = timeout or int(os.getenv("NP_TIMEOUT_SECONDS", "5"))

    def call(self, model_name, called_method, method_properties=None):
        if not self.api_key:
            return {"ok": False, "error_type": "config", "message": "API-ключ Нової Пошти не налаштовано.", "data": []}

        payload = {
            "apiKey": self.api_key,
            "modelName": model_name,
            "calledMethod": called_method,
            "methodProperties": method_properties or {},
        }

        request = Request(
            self.base_url,
            data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except URLError:
            return {"ok": False, "error_type": "timeout", "message": "Помилка запиту до Нової Пошти.", "data": []}
        except Exception:
            return {"ok": False, "error_type": "unexpected", "message": "Непередбачена помилка Нової Пошти.", "data": []}

        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            return {"ok": False, "error_type": "malformed", "message": "Некоректна відповідь від Нової Пошти.", "data": []}

        success = bool(parsed.get("success"))
        data = parsed.get("data") or []
        errors = parsed.get("errors") or []
        if not success:
            return {"ok": False, "error_type": "api", "message": errors[0] if errors else "Помилка API Нової Пошти.", "data": []}

        return {"ok": True, "error_type": None, "message": "", "data": data}


class NovaPoshtaService:
    KHARKIV_CITY_REF = "db5c88e0-391c-11dd-90d9-001a92567626"
    DECLARED_VALUE_COMMISSION_RATE = Decimal("0.005")

    def __init__(self, client=None):
        self.client = client or NovaPoshtaClient()

    @staticmethod
    def _normalize_cities_from_search_settlements(rows):
        normalized = []
        seen_refs = set()
        for block in rows or []:
            addresses = block.get("Addresses") if isinstance(block, dict) else None
            if not isinstance(addresses, list):
                continue

            for row in addresses:
                if not isinstance(row, dict):
                    continue
                name = (row.get("Present") or row.get("MainDescription") or row.get("Description") or "").strip()
                ref = (row.get("DeliveryCity") or row.get("Ref") or "").strip()
                if not name or not ref or ref in seen_refs:
                    continue
                normalized.append({"name": name, "ref": ref})
                seen_refs.add(ref)
        return normalized

    @staticmethod
    def _normalize_cities_from_get_cities(rows):
        normalized = []
        seen_refs = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("Description") or row.get("Present") or row.get("MainDescription") or "").strip()
            ref = (row.get("Ref") or row.get("DeliveryCity") or "").strip()
            if not name or not ref or ref in seen_refs:
                continue
            normalized.append({"name": name, "ref": ref})
            seen_refs.add(ref)
        return normalized

    @staticmethod
    def _normalize_warehouses(rows):
        normalized = []
        seen_refs = set()
        for row in rows or []:
            if not isinstance(row, dict):
                continue
            name = (row.get("Description") or row.get("ShortAddress") or row.get("DescriptionRu") or "").strip()
            warehouse_ref = (row.get("Ref") or "").strip()
            if not name or not warehouse_ref or warehouse_ref in seen_refs:
                continue
            normalized.append({"name": name, "ref": warehouse_ref})
            seen_refs.add(warehouse_ref)
        return normalized

    @staticmethod
    def _as_decimal(value):
        text = str(value or "").strip().replace(",", ".")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation:
            return None

    def search_cities(self, query):
        term = (query or "").strip()
        if len(term) < 2:
            return {"ok": True, "error_type": None, "message": "", "data": []}

        settlements_response = self.client.call("Address", "searchSettlements", {"CityName": term, "Limit": 20, "Page": 1})
        if settlements_response["ok"]:
            normalized = self._normalize_cities_from_search_settlements(settlements_response["data"])
            if normalized:
                return {"ok": True, "error_type": None, "message": "", "data": normalized}

        cities_response = self.client.call("Address", "getCities", {"FindByString": term, "Limit": 20})
        if not cities_response["ok"]:
            if settlements_response["ok"]:
                return {"ok": True, "error_type": None, "message": "", "data": []}
            return {**settlements_response, "data": []}

        normalized = self._normalize_cities_from_get_cities(cities_response["data"])
        return {"ok": True, "error_type": None, "message": "", "data": normalized}

    def get_warehouses(self, city_ref):
        ref = (city_ref or "").strip()
        if not ref:
            return {"ok": False, "error_type": "validation", "message": "Місто не вибрано.", "data": []}

        primary_response = self.client.call("AddressGeneral", "getWarehouses", {"CityRef": ref, "Limit": 200})
        normalized = self._normalize_warehouses(primary_response["data"]) if primary_response["ok"] else []
        if normalized:
            return {"ok": True, "error_type": None, "message": "", "data": normalized}

        fallback_response = self.client.call("Address", "getWarehouses", {"CityRef": ref, "Limit": 200})
        fallback_normalized = self._normalize_warehouses(fallback_response["data"]) if fallback_response["ok"] else []
        if fallback_normalized:
            return {"ok": True, "error_type": None, "message": "", "data": fallback_normalized}

        if primary_response["ok"] or fallback_response["ok"]:
            return {"ok": False, "error_type": "empty", "message": "Для обраного міста відділень не знайдено.", "data": []}

        return {**primary_response, "data": []}

    def estimate_delivery_range(self, city_ref, warehouse_ref, declared_cost_uah=1000):
        if not city_ref or not warehouse_ref:
            return {"ok": False, "error_type": "validation", "message": "Точку доставки вказано не повністю.", "data": None}

        sender_city_ref = self.KHARKIV_CITY_REF
        declared_cost = self._as_decimal(declared_cost_uah) or Decimal("1000")
        if declared_cost < 0:
            declared_cost = Decimal("0")
        response = self.client.call(
            "InternetDocument",
            "getDocumentPrice",
            {
                "CitySender": sender_city_ref,
                "CityRecipient": city_ref,
                "Weight": "1",
                "ServiceType": "WarehouseWarehouse",
                "Cost": str(int(declared_cost)),
                "CargoType": "Cargo",
                "SeatsAmount": "1",
            },
        )
        if not response["ok"]:
            return {"ok": False, "error_type": response.get("error_type"), "message": response.get("message", ""), "data": None}

        row = response["data"][0] if response["data"] else {}
        delivery_cost = self._as_decimal(row.get("Cost")) if isinstance(row, dict) else None
        if delivery_cost is None:
            return {"ok": False, "error_type": "api", "message": "Не вдалося отримати вартість доставки.", "data": None}

        declared_value_commission = (declared_cost * self.DECLARED_VALUE_COMMISSION_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_delivery_cost = (delivery_cost + declared_value_commission).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        return {"ok": True, "error_type": None, "message": "", "data": {"min": total_delivery_cost, "max": total_delivery_cost}}

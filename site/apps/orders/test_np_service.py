import json
from unittest.mock import patch
from urllib.error import URLError

from django.test import SimpleTestCase

from apps.orders.np_service import NovaPoshtaClient, NovaPoshtaService


class RouteStubClient:
    def __init__(self, responses):
        self.responses = responses
        self.calls = []

    def call(self, model_name, called_method, method_properties=None):
        self.calls.append((model_name, called_method, method_properties or {}))
        return self.responses.get(
            (model_name, called_method),
            {"ok": False, "error_type": "api", "message": "missing stub", "data": []},
        )


class NovaPoshtaServiceTests(SimpleTestCase):
    def test_client_sends_expected_request_and_returns_provider_data(self):
        with patch("apps.orders.np_service.urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = b'{"success": true, "data": [{"Ref": "city"}]}'
            result = NovaPoshtaClient(api_key="test", timeout=2).call(
                "Address", "getCities", {"FindByString": "Kyiv"}
            )
        self.assertEqual(result, {"ok": True, "error_type": None, "message": "", "data": [{"Ref": "city"}]})
        sent_request = request.call_args.args[0]
        self.assertEqual(json.loads(sent_request.data), {
            "apiKey": "test", "modelName": "Address", "calledMethod": "getCities",
            "methodProperties": {"FindByString": "Kyiv"},
        })
        self.assertEqual(request.call_args.kwargs["timeout"], 2)

    def test_client_keeps_network_and_malformed_response_errors(self):
        client = NovaPoshtaClient(api_key="test")
        with patch("apps.orders.np_service.urlopen", side_effect=URLError("offline")):
            self.assertEqual(client.call("Address", "getCities")["error_type"], "timeout")
        with patch("apps.orders.np_service.urlopen") as request:
            request.return_value.__enter__.return_value.read.return_value = b'not-json'
            self.assertEqual(client.call("Address", "getCities")["error_type"], "malformed")

    def test_search_cities_normalizes_search_settlements_response(self):
        client = RouteStubClient(
            {
                (
                    "Address",
                    "searchSettlements",
                ): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [
                        {
                            "Addresses": [
                                {
                                    "Present": "м. Київ, Київська обл.",
                                    "DeliveryCity": "delivery-city-ref-1",
                                    "Ref": "settlement-ref-1",
                                },
                                {
                                    "Present": "",
                                    "DeliveryCity": "delivery-city-ref-2",
                                },
                                {
                                    "Present": "м. Львів, Львівська обл.",
                                    "DeliveryCity": "",
                                    "Ref": "settlement-ref-2",
                                },
                            ]
                        }
                    ],
                }
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.search_cities("Ки")

        self.assertTrue(result["ok"])
        self.assertEqual(
            result["data"],
            [
                {"name": "м. Київ, Київська обл.", "ref": "delivery-city-ref-1"},
                {"name": "м. Львів, Львівська обл.", "ref": "settlement-ref-2"},
            ],
        )
        self.assertEqual(client.calls[0][0:2], ("Address", "searchSettlements"))
        self.assertEqual(client.calls[0][2], {"CityName": "Ки", "Limit": 20, "Page": 1})

    def test_search_cities_falls_back_to_get_cities_when_needed(self):
        client = RouteStubClient(
            {
                ("Address", "searchSettlements"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [{"Addresses": []}],
                },
                ("Address", "getCities"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [
                        {"Description": "Kyiv", "Ref": "1"},
                        {"Description": "", "Ref": "2"},
                        {"Description": "Lviv", "Ref": ""},
                    ],
                },
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.search_cities("Ky")

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], [{"name": "Kyiv", "ref": "1"}])
        self.assertEqual([call[1] for call in client.calls], ["searchSettlements", "getCities"])

    def test_search_cities_returns_primary_error_when_all_methods_fail(self):
        client = RouteStubClient(
            {
                ("Address", "searchSettlements"): {
                    "ok": False,
                    "error_type": "timeout",
                    "message": "timeout",
                    "data": [],
                },
                ("Address", "getCities"): {
                    "ok": False,
                    "error_type": "api",
                    "message": "api error",
                    "data": [],
                },
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.search_cities("Ки")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "timeout")

    def test_warehouses_fallback_to_address_get_warehouses(self):
        client = RouteStubClient(
            {
                ("AddressGeneral", "getWarehouses"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [],
                },
                ("Address", "getWarehouses"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [{"ShortAddress": "Відділення 1", "Ref": "wh-1"}],
                },
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.get_warehouses("city-ref")

        self.assertTrue(result["ok"])
        self.assertEqual(result["data"], [{"name": "Відділення 1", "ref": "wh-1"}])

    def test_warehouses_empty_returns_retry_error(self):
        client = RouteStubClient(
            {
                ("AddressGeneral", "getWarehouses"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [],
                },
                ("Address", "getWarehouses"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [],
                },
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.get_warehouses("city-ref")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "empty")

    def test_estimate_requires_refs(self):
        service = NovaPoshtaService(client=RouteStubClient({}))
        result = service.estimate_delivery_range("", "")
        self.assertFalse(result["ok"])

    def test_estimate_uses_document_price_api(self):
        client = RouteStubClient(
            {
                ("InternetDocument", "getDocumentPrice"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [{"Cost": "88.50"}],
                }
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.estimate_delivery_range("city-recipient", "warehouse-ref", declared_cost_uah=35000)

        self.assertTrue(result["ok"])
        self.assertEqual(str(result["data"]["min"]), "263.50")
        self.assertEqual(str(result["data"]["max"]), "263.50")
        self.assertEqual(client.calls[0][0:2], ("InternetDocument", "getDocumentPrice"))
        self.assertEqual(client.calls[0][2]["CitySender"], NovaPoshtaService.KHARKIV_CITY_REF)
        self.assertEqual(client.calls[0][2]["CityRecipient"], "city-recipient")
        self.assertEqual(client.calls[0][2]["Cost"], "35000")

    def test_estimate_returns_error_when_price_missing(self):
        client = RouteStubClient(
            {
                ("InternetDocument", "getDocumentPrice"): {
                    "ok": True,
                    "error_type": None,
                    "message": "",
                    "data": [{}],
                }
            }
        )
        service = NovaPoshtaService(client=client)

        result = service.estimate_delivery_range("city-recipient", "warehouse-ref")

        self.assertFalse(result["ok"])
        self.assertEqual(result["error_type"], "api")

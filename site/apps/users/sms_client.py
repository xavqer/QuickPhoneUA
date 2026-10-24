import json
import uuid
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings


class SmsClubClient:
    def __init__(self, api_url=None, api_token=None, sender_name=None, timeout=None, fake_delivery=None):
        self.api_url = api_url or settings.SMSCLUB_API_URL
        self.api_token = api_token if api_token is not None else settings.SMSCLUB_API_TOKEN
        self.sender_name = sender_name if sender_name is not None else settings.SMSCLUB_SENDER_NAME
        self.timeout = timeout if timeout is not None else settings.SMSCLUB_TIMEOUT_SECONDS
        self.fake_delivery = fake_delivery if fake_delivery is not None else settings.SMS_VERIFICATION_FAKE_DELIVERY

    def send_sms(self, phone, message):
        if self.fake_delivery:
            if settings.DEBUG:
                print(f"[DEMO SMS] {phone}: {message}")
            return {"ok": True, "error_type": None, "message": "", "message_id": f"fake-{uuid.uuid4().hex[:12]}"}
        if not self.api_token:
            return {
                "ok": False,
                "error_type": "config",
                "message": "Не налаштовано SMSCLUB_API_TOKEN для відправки коду.",
                "message_id": "",
            }
        if not self.sender_name:
            return {
                "ok": False,
                "error_type": "config",
                "message": "Не налаштовано SMSCLUB_SENDER_NAME для відправки коду.",
                "message_id": "",
            }

        payload = {"phone": [str(phone or "").lstrip("+")], "src_addr": self.sender_name, "message": message}
        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_token}"},
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            return self._parse_response(body, fallback_message="Сервіс SMS повернув помилку.")
        except URLError:
            return {
                "ok": False,
                "error_type": "timeout",
                "message": "Не вдалося звернутися до сервісу SMS.",
                "message_id": "",
            }
        except Exception:
            return {
                "ok": False,
                "error_type": "unexpected",
                "message": "Сталася непередбачена помилка під час відправки SMS.",
                "message_id": "",
            }

        return self._parse_response(body, fallback_message="Сервіс SMS повернув некоректну відповідь.")

    def _parse_response(self, body, fallback_message):
        try:
            parsed = json.loads(body)
            if not isinstance(parsed, dict):
                raise ValueError("Expected an SMS response object.")
            success_request = parsed.get("success_request") or {}
            if not isinstance(success_request, dict):
                raise ValueError("Expected success_request to be an object.")
        except (ValueError, TypeError):
            return {"ok": False, "error_type": "malformed", "message": fallback_message, "message_id": ""}

        info = success_request.get("info") or {}
        add_info = success_request.get("add_info") or {}

        if isinstance(info, dict) and info:
            message_id = next(iter(info.keys()))
            return {"ok": True, "error_type": None, "message": "", "message_id": str(message_id)}

        if isinstance(add_info, dict) and add_info:
            message = str(next(iter(add_info.values())))
            return {"ok": False, "error_type": "api", "message": message, "message_id": ""}

        return {"ok": False, "error_type": "api", "message": fallback_message, "message_id": ""}

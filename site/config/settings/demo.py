from .production import *  # noqa: F403,F401

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / ".demo" / "db.sqlite3",  # noqa: F405
    }
}

REGISTRATION_ENABLED = False
SMS_VERIFICATION_ENABLED = False
SMS_VERIFICATION_FAKE_DELIVERY = False
SMS_VERIFICATION_TEST_CODE = ""

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

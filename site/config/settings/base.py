import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-env")
DEBUG = os.getenv("DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
SITE_BASE_URL = os.getenv("SITE_BASE_URL", "").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.sitemaps",
    "django.contrib.staticfiles",
    "django_htmx",
    "apps.catalog",
    "apps.orders",
    "apps.users",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "libraries": {"price_tags": "apps.catalog.templatetags.price_tags"},
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.catalog.context_processors.header_catalog_menu",
                "apps.catalog.context_processors.site_contact_links",
                "apps.catalog.context_processors.seo_defaults",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("DB_NAME", ""),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "localhost"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uk"
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True
DEFAULT_CHARSET = "utf-8"

STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "users.CustomUser"

SMSCLUB_API_URL = os.getenv("SMSCLUB_API_URL", "https://im.smsclub.mobi/sms/send")
SMSCLUB_API_TOKEN = os.getenv("SMSCLUB_API_TOKEN", "")
SMSCLUB_SENDER_NAME = os.getenv("SMSCLUB_SENDER_NAME", "")
SMSCLUB_TIMEOUT_SECONDS = int(os.getenv("SMSCLUB_TIMEOUT_SECONDS", "5"))
REGISTRATION_ENABLED = os.getenv("REGISTRATION_ENABLED", "true").lower() == "true"
SMS_VERIFICATION_ENABLED = os.getenv("SMS_VERIFICATION_ENABLED", "false").lower() == "true"
SMS_VERIFICATION_CODE_LENGTH = int(os.getenv("SMS_VERIFICATION_CODE_LENGTH", "6"))
SMS_VERIFICATION_CODE_TTL_MINUTES = int(os.getenv("SMS_VERIFICATION_CODE_TTL_MINUTES", "10"))
SMS_VERIFICATION_RESEND_SECONDS = int(os.getenv("SMS_VERIFICATION_RESEND_SECONDS", "60"))
SMS_LOGIN_REVERIFY_DAYS = int(os.getenv("SMS_LOGIN_REVERIFY_DAYS", "30"))
SMS_VERIFICATION_FAKE_DELIVERY = os.getenv("SMS_VERIFICATION_FAKE_DELIVERY", "true" if DEBUG else "false").lower() == "true"
SMS_VERIFICATION_TEST_CODE = os.getenv("SMS_VERIFICATION_TEST_CODE", "")

CONTACT_PHONE_DISPLAY = os.getenv("CONTACT_PHONE_DISPLAY", "+38 (066) 741 29 83")
CONTACT_PHONE_E164 = os.getenv("CONTACT_PHONE_E164", "+380667412983")
CONTACT_MANAGER_LABEL = os.getenv("CONTACT_MANAGER_LABEL", "Менеджер QuickPhone UA")
CONTACT_MANAGER_TELEGRAM_URL = os.getenv("CONTACT_MANAGER_TELEGRAM_URL", "https://t.me/quick_phone_manager")
SOCIAL_INSTAGRAM_URL = os.getenv("SOCIAL_INSTAGRAM_URL", "https://www.instagram.com/quick_phone_ua/")
SOCIAL_TELEGRAM_URL = os.getenv("SOCIAL_TELEGRAM_URL", "https://t.me/quick_phone")
SOCIAL_TIKTOK_URL = os.getenv("SOCIAL_TIKTOK_URL", "https://www.tiktok.com/@quick_phone_ua")

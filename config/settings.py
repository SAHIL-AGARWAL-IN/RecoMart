"""Django settings for RecoMart.

Secrets and environment-specific values come from the .env file (python-dotenv).
"""
import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


INSECURE_DEFAULT_KEY = "dev-only-insecure-key-change-me"
SECRET_KEY = os.getenv("SECRET_KEY", INSECURE_DEFAULT_KEY)
DEBUG = env_bool("DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]

if not DEBUG and SECRET_KEY in {INSECURE_DEFAULT_KEY, "change-me-to-a-long-random-string"}:
    raise ImproperlyConfigured("Set a real SECRET_KEY in .env before running with DEBUG=False.")

# Production over HTTPS (set HTTPS=True in .env on the live server): secure cookies, redirect to
# https:// and tell browsers to always use HTTPS (HSTS).
if env_bool("HTTPS", False):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.getenv("HSTS_SECONDS", "3600"))
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Project apps
    "accounts.apps.AccountsConfig",
    "store.apps.StoreConfig",
    "recommender.apps.RecommenderConfig",
    "dashboard.apps.DashboardConfig",
    "assistant.apps.AssistantConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
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
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "store.context_processors.store_nav",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# ---------------------------------------------------------------------------
# Database: SQLite by default, PostgreSQL when DB_ENGINE=postgres
# ---------------------------------------------------------------------------
if os.getenv("DB_ENGINE", "").lower() == "postgres":
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("DB_NAME", "recomart"),
            "USER": os.getenv("DB_USER", "postgres"),
            "PASSWORD": os.getenv("DB_PASSWORD", ""),
            "HOST": os.getenv("DB_HOST", "127.0.0.1"),
            "PORT": os.getenv("DB_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "accounts.User"
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "store:home"
LOGOUT_REDIRECT_URL = "store:home"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Internationalisation: Indian locale, prices in INR
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-in"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
CURRENCY_SYMBOL = "₹"


# ---------------------------------------------------------------------------
# Static and media files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"


# ---------------------------------------------------------------------------
# Recommendation engine
# ---------------------------------------------------------------------------
RECOMMENDER = {
    "ARTIFACTS_DIR": BASE_DIR / "recommender" / "artifacts",  # trained Joblib models
    "TOP_N": 8,                 # cards shown in a recommendation strip
    "CACHE_TOP_N": 20,          # similar items stored per product after training
    "K_MIN": 3,                 # K-Means: range of K values tried
    "K_MAX": 12,
    "RANDOM_STATE": 42,
    # Hybrid ranking: final = similarity*w1 + popularity*w2 + recency*w3
    "HYBRID_WEIGHTS": {"similarity": 0.60, "popularity": 0.25, "recency": 0.15},
    "OUT_OF_STOCK_PENALTY": 0.5,
    "AB_TEST_ENABLED": True,    # A = similar items, B = hybrid ranking
}

# Weight of each interaction type when measuring popularity or a user's taste.
INTERACTION_WEIGHTS = {"view": 1, "wishlist": 2, "cart": 2, "review": 2, "purchase": 3}

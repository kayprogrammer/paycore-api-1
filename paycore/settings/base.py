import os
from pathlib import Path
from decouple import config
import json
import warnings
import firebase_admin
from firebase_admin import credentials
import dj_database_url

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Suppress Django ASGI StreamingHttpResponse warning for static files
# This is a known Django/Django Ninja issue when serving Swagger UI assets
warnings.filterwarnings(
    "ignore",
    message="StreamingHttpResponse must consume synchronous iterators",
    category=Warning,
)


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config("SECRET_KEY")

# SECURITY WARNING: don't run with debug turned on in production!
ALLOWED_HOSTS = config("ALLOWED_HOSTS").split(" ")

# Application definition
DJANGO_APPS = [
    "jazzmin",  # not a django app but must be included before admin
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",  # not a django app but must be included before staticfiles
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

SITE_ID = 1

THIRD_PARTY_APPS = [
    "cloudinary",
    "cloudinary_storage",
    "ninja",
    "django_celery_beat",
    "django_celery_results",
    "django_prometheus",
    "channels",
    "fcm_django",
    "corsheaders",
]

LOCAL_APPS = [
    "apps.common",
    "apps.accounts",
    "apps.profiles",
    "apps.wallets",
    "apps.cards",
    "apps.bills",
    "apps.transactions",
    "apps.payments",
    "apps.loans",
    "apps.investments",
    "apps.notifications",
    "apps.audit_logs",
    "apps.compliance",
    "apps.support",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

AUTH_USER_MODEL = "accounts.User"

CORS_ALLOW_HEADERS = (
    "x-requested-with",
    "content-type",
    "accept",
    "origin",
    "authorization",
    "accept-encoding",
    "access-control-allow-origin",
    "content-disposition",
)

CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS").split(" ")
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = ("GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS")

# Celery Configuration
CELERY_TIMEZONE = "UTC"
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
CELERY_RESULT_EXPIRES = 3600  # 1 hour
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Celery Broker and Backend URLs (will be overridden by environment variables)
CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL", default="amqp://guest:guest@localhost:5672//"
)
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND", default="redis://localhost:6379/0"
)

# Django Celery Beat (for scheduled tasks)
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Django Celery Results (for result storage in database)
CELERY_RESULT_BACKEND_DB_SHORT_LIVED_SESSIONS = True


MIDDLEWARE = [
    "django_prometheus.middleware.PrometheusBeforeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "apps.common.middlewares.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "ninja.compatibility.files.fix_request_files_middleware",
    "apps.common.middlewares.ClientTypeMiddleware",
    "apps.audit_logs.middleware.AuditLoggingMiddleware",  # Automatic audit logging
    "django_prometheus.middleware.PrometheusAfterMiddleware",
]

ROOT_URLCONF = "paycore.urls"

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
            ],
        },
    },
]

WSGI_APPLICATION = "paycore.wsgi.application"
ASGI_APPLICATION = "paycore.asgi.application"


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Check if DATABASE_URL is provided (Fly.io Postgres attachment)
DATABASE_URL = config("DATABASE_URL", default=None)

if DATABASE_URL:
    # Use Fly Postgres (or any DATABASE_URL-based setup)
    DATABASES = {
        "default": dj_database_url.config(
            default=DATABASE_URL,
            conn_max_age=0,  # Don't persist connections
            conn_health_checks=True,  # Enable connection health checks
            ssl_require=False,  # Fly's internal network doesn't need SSL
        )
    }
    # Add additional options for Fly Postgres
    DATABASES["default"]["OPTIONS"] = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",  # 30 second statement timeout
    }
else:
    # Use legacy individual config variables (local development or Neon)
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": config("DB_NAME"),
            "USER": config("DB_USER"),
            "PASSWORD": config("DB_PASSWORD"),
            "HOST": config("DB_HOST", default="localhost"),
            "PORT": config("DB_PORT", default="5432"),
            "CONN_MAX_AGE": 0,  # Don't persist connections (helps with serverless DBs)
            "OPTIONS": {
                "connect_timeout": 10,
                "options": "-c statement_timeout=30000",  # 30 second statement timeout
            },
        }
    }

# Redis details
# Support both URL-based (Upstash) and host/port-based (local) Redis configurations
REDIS_URL = config("REDIS_URL", default=None)
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default="6379", cast=int)
REDIS_DB = config("REDIS_DB", default="0", cast=int)
REDIS_PASSWORD = config("REDIS_PASSWORD", default=None)

# Build Redis location based on available configuration
if REDIS_URL:
    # Use full Redis URL (Upstash or other managed Redis)
    REDIS_LOCATION = REDIS_URL
else:
    # Build Redis URL from host, port, password, and db
    if REDIS_PASSWORD:
        REDIS_LOCATION = (
            f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
        )
    else:
        REDIS_LOCATION = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"

# Cache configuration for rate limiting
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_LOCATION,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SERIALIZER": "django_redis.serializers.json.JSONSerializer",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "retry_on_timeout": True,
            },
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            "IGNORE_EXCEPTIONS": True,  # Gracefully handle Redis connection failures
        },
        "KEY_PREFIX": "paycore",
        "TIMEOUT": 300,  # Default TTL: 5 minutes
    }
}

# Cache key prefix for the caching system
CACHE_KEY_PREFIX = "paycore"


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_URL = "/static/"
MEDIA_URL = "/media/"
STATICFILES_DIRS = [BASE_DIR / "static/"]

MEDIA_ROOT = BASE_DIR / "static/media"
DEFAULT_FILE_STORAGE = "django_cloudinary_storage.storage.MediaCloudinaryStorage"
STORAGES = {
    "default": {
        "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
    },
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

CLOUDINARY_STORAGE = {
    "CLOUD_NAME": config("CLOUDINARY_CLOUD_NAME"),
    "API_KEY": config("CLOUDINARY_API_KEY"),
    "API_SECRET": config("CLOUDINARY_API_SECRET"),
}
# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

ACCESS_TOKEN_EXPIRE_MINUTES = config("ACCESS_TOKEN_EXPIRE_MINUTES")
REFRESH_TOKEN_EXPIRE_MINUTES = config("REFRESH_TOKEN_EXPIRE_MINUTES")
TRUST_TOKEN_EXPIRE_DAYS = int(config("TRUST_TOKEN_EXPIRE_DAYS", 30))

# Email Settings
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST")
EMAIL_PORT = config("EMAIL_PORT")
EMAIL_HOST_USER = config("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD")
EMAIL_USE_SSL = config("EMAIL_USE_SSL")
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL")

GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = config("GOOGLE_CLIENT_SECRET")

# Celery details
CELERY_BROKER_URL = config("CELERY_BROKER_URL")
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND")

# Structured Logging - No file logging, all to stdout for container environments
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "format": '{"level": "%(levelname)s", "timestamp": "%(asctime)s", "logger": "%(name)s", "message": "%(message)s", "module": "%(module)s"}',
        },
        "simple": {
            "()": "logging.Formatter",
            "format": "\033[32m%(levelname)s\033[0m:     \033[36m%(name)s\033[0m - %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
            "stream": "ext://sys.stdout",
        },
        "error_console": {
            "class": "logging.StreamHandler",
            "formatter": "json",
            "level": "ERROR",
            "stream": "ext://sys.stderr",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.accounts.tasks": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "celery.task": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps.common.monitoring": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console", "error_console"],
        "level": "INFO",
    },
}

FRONTEND_URL = config("FRONTEND_URL")

JAZZMIN_SETTINGS = {
    # title of the window (Will default to current_admin_site.site_title if absent or None)
    "site_title": "PAYCORE ADMIN",
    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "PAYCORE",
    # Logo to use for your site, must be present in static files, used for brand on top left
    "site_logo": "media/logo.jpg",
    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",
    # Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
    "login_logo": "media/logo.jpg",
    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": "media/logo.jpg",
    # Welcome text on the login screen
    "welcome_sign": "Welcome to the Paycore Admin Section",
    # Copyright on the footer
    "copyright": "Paycore Ltd",
    # The model admin to search from the search bar, search bar omitted if excluded
    "search_model": ["accounts.User"],
    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": "avatar_url",
    ############
    # Top Menu #
    ############
    # Links to put along the top menu
    "topmenu_links": [
        # Url that gets reversed (Permissions can be added)
        {
            "name": "Home",
            "url": "admin:index",
            "permissions": ["auth.view_user"],
        },
        # model admin to link to (Permissions checked against model)
        # {"model": "accounts.User"},
        # App with dropdown menu to all its models pages (Permissions checked against models)
        {"app": "accounts"},
        {"app": "blog"},
    ],
    #############
    # User Menu #
    #############
    # Additional links to include in the user menu on the top right ("app" url type is not allowed)
    "usermenu_links": [
        {"name": "PAYCORE API DOCS", "url": "/", "new_window": True},
        {
            "name": "GITHUB REPO",
            "url": "https://github.com/kayprogrammer/paycore-api-1",
            "new_window": True,
        },
        {
            "name": "FRONTEND LINK",
            "url": FRONTEND_URL,
            "new_window": True,
        },
        {"model": "accounts.user"},
    ],
    #############
    # Side Menu #
    #############
    # Whether to display the side menu
    "show_sidebar": True,
    # Whether to aut expand the menu
    "navigation_expanded": True,
    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],
    # Hide these models when generating side menu (e.g auth.user)
    "hide_models": [],
    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": [
        "auth",
        "accounts",
        "compliance",
        "wallets",
        "cards",
        "transactions",
        "payments",
        "bills",
        "loans",
        "investments",
        "support",
        "notifications",
    ],
    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # for the full list of 5.13.0 free icon classes
    "icons": {
        "accounts.Group": "fas fa-users",
        "accounts.user": "fas fa-user-cog",
        "compliance.kycverification": "fas fa-id-card",
        "compliance.kycdocument": "fas fa-file-alt",
        "compliance.compliancereport": "fas fa-file-contract",
        "compliance.amlcheck": "fas fa-shield-alt",
        "compliance.sanctionsscreening": "fas fa-ban",
        "compliance.transactionmonitoring": "fas fa-search-dollar",
        "wallets.currency": "fas fa-coins",
        "wallets.wallet": "fas fa-wallet",
        "cards.card": "fas fa-credit-card",
        "transactions.transaction": "fas fa-exchange-alt",
        "transactions.transactiondispute": "fas fa-exclamation-triangle",
        "transactions.transactionhold": "fas fa-pause-circle",
        "transactions.transactionfee": "fas fa-percent",
        "transactions.transactionlog": "fas fa-file-alt",
        "payments.paymentlink": "fas fa-link",
        "payments.invoice": "fas fa-file-invoice",
        "payments.invoiceitem": "fas fa-list-ul",
        "payments.payment": "fas fa-money-check-alt",
        "payments.merchantapikey": "fas fa-key",
        "bills.billprovider": "fas fa-building",
        "bills.billpackage": "fas fa-box",
        "bills.billpayment": "fas fa-receipt",
        "bills.billbeneficiary": "fas fa-user-tag",
        "bills.billpaymentschedule": "fas fa-calendar-alt",
        "loans.loanproduct": "fas fa-hand-holding-usd",
        "loans.loanapplication": "fas fa-file-signature",
        "loans.loanrepaymentschedule": "fas fa-calendar-check",
        "loans.loanrepayment": "fas fa-money-bill-wave",
        "loans.creditscore": "fas fa-chart-line",
        "loans.autorepayment": "fas fa-sync-alt",
        "investments.investmentproduct": "fas fa-chart-pie",
        "investments.investment": "fas fa-piggy-bank",
        "investments.investmentreturn": "fas fa-arrow-up",
        "investments.investmentportfolio": "fas fa-briefcase",
        "support.supportticket": "fas fa-ticket-alt",
        "support.ticketmessage": "fas fa-comment",
        "support.ticketattachment": "fas fa-paperclip",
        "support.faq": "fas fa-question-circle",
        "support.cannedresponse": "fas fa-reply",
        "support.ticketescalation": "fas fa-level-up-alt",
        "notifications.notification": "fas fa-bell",
        "notifications.notificationtemplate": "fas fa-envelope",
        "audit_logs.auditlog": "fas fa-file-alt",
        "sites.site": "fas fa-globe",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",
    #############
    # UI Tweaks #
    #############
    "show_ui_builder": False,
    "changeform_format": "horizontal_tabs",
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {
        "auth.user": "collapsible",
        "auth.group": "vertical_tabs",
    },
    # "related_modal_active": True # Won't work in some browsers
}
# KYC Settings
KYC_PROVIDER = config("KYC_PROVIDER", default="onfido")

ONFIDO_BASE_URL = config("ONFIDO_BASE_URL", default="https://api.eu.onfido.com/v3.6")
ONFIDO_API_KEY = config("ONFIDO_API_KEY")
ONFIDO_WEBHOOK_TOKEN = config("ONFIDO_WEBHOOK_TOKEN")

# Payment Provider Settings
# Controls whether all payment providers run in test/sandbox mode
# Set to False in production to use live credentials
PAYMENT_PROVIDERS_TEST_MODE = config(
    "PAYMENT_PROVIDERS_TEST_MODE", default=True, cast=bool
)

# Paystack Configuration
# Get your keys from: https://dashboard.paystack.com/#/settings/developers
PAYSTACK_TEST_SECRET_KEY = config("PAYSTACK_TEST_SECRET_KEY", default=None)
PAYSTACK_TEST_PUBLIC_KEY = config("PAYSTACK_TEST_PUBLIC_KEY", default=None)
PAYSTACK_LIVE_SECRET_KEY = config("PAYSTACK_LIVE_SECRET_KEY", default=None)
PAYSTACK_LIVE_PUBLIC_KEY = config("PAYSTACK_LIVE_PUBLIC_KEY", default=None)

# Flutterwave Configuration
# Get your keys from: https://dashboard.flutterwave.com/settings/apis
# Used for: Virtual cards (USD, NGN, GBP)
FLUTTERWAVE_TEST_SECRET_KEY = config("FLUTTERWAVE_TEST_SECRET_KEY", default=None)
FLUTTERWAVE_LIVE_SECRET_KEY = config("FLUTTERWAVE_LIVE_SECRET_KEY", default=None)
FLUTTERWAVE_WEBHOOK_SECRET = config("FLUTTERWAVE_WEBHOOK_SECRET", default=None)

# Sudo Africa Configuration
# Get your keys from: https://dashboard.sudo.africa/developers/keys
# Used for: Virtual cards (USD, NGN)
SUDO_TEST_SECRET_KEY = config("SUDO_TEST_SECRET_KEY", default=None)
SUDO_LIVE_SECRET_KEY = config("SUDO_LIVE_SECRET_KEY", default=None)
SUDO_WEBHOOK_SECRET = config("SUDO_WEBHOOK_SECRET", default=None)

# Card Provider Settings
# Set to True to use test/sandbox mode, False for production
CARD_PROVIDERS_TEST_MODE = config("CARD_PROVIDERS_TEST_MODE", default=True, cast=bool)

# Use Internal Providers Globally
# When True: Uses internal providers for wallets, cards, and bills (no external API calls)
# When False: Uses external providers (Paystack, Flutterwave, Sudo, etc.)
# Perfect for development when external providers aren't configured
USE_INTERNAL_PROVIDER = config("USE_INTERNAL_PROVIDER", default=False, cast=bool)
# Wise Configuration (Future use)
WISE_TEST_API_KEY = config("WISE_TEST_API_KEY", default=None)
WISE_LIVE_API_KEY = config("WISE_LIVE_API_KEY", default=None)


# Django Channels Configuration
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": (
                [REDIS_LOCATION]
                if REDIS_URL
                else [
                    (
                        REDIS_HOST,
                        REDIS_PORT,
                    )
                ]
            ),
            "capacity": 1500,
            "expiry": 10,
        },
    },
}

# Firebase Admin SDK Configuration

FIREBASE_APP = None
FIREBASE_CREDENTIALS_JSON = config("FIREBASE_CREDENTIALS_JSON", default=None)
FIREBASE_CREDENTIALS_PATH = config("FIREBASE_CREDENTIALS_PATH", default=None)

# Initialize Firebase Admin SDK
if FIREBASE_CREDENTIALS_JSON and FIREBASE_CREDENTIALS_JSON.strip():
    # Option 1: Using JSON string from environment variable (Production)
    try:
        cred_dict = json.loads(FIREBASE_CREDENTIALS_JSON)
        cred = credentials.Certificate(cred_dict)
        FIREBASE_APP = firebase_admin.initialize_app(cred)
        print("✓ Firebase initialized from environment variable")
    except json.JSONDecodeError as e:
        print(f"✗ Failed to parse Firebase JSON credentials: {e}")
    except Exception as e:
        print(f"✗ Failed to initialize Firebase from JSON: {e}")
elif FIREBASE_CREDENTIALS_PATH and FIREBASE_CREDENTIALS_PATH.strip():
    # Option 2: Using JSON file path (Development)
    try:
        service_account_path = os.path.join(BASE_DIR, FIREBASE_CREDENTIALS_PATH)
        if os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            FIREBASE_APP = firebase_admin.initialize_app(cred)
            print(f"✓ Firebase initialized from file: {FIREBASE_CREDENTIALS_PATH}")
        else:
            print(f"✗ Firebase credentials file not found: {service_account_path}")
    except Exception as e:
        print(f"✗ Failed to initialize Firebase from file: {e}")
else:
    print("⚠ Firebase credentials not configured. Push notifications will not work.")

# FCM Django Settings
FCM_DJANGO_SETTINGS = {
    "DEFAULT_FIREBASE_APP": FIREBASE_APP,
    "APP_VERBOSE_NAME": "PayCore",
    "ONE_DEVICE_PER_USER": True,
    "DELETE_INACTIVE_DEVICES": True,
    "TIMEOUT": 30,
}

# Notification Settings
NOTIFICATION_RETENTION_DAYS = config(
    "NOTIFICATION_RETENTION_DAYS", default=90, cast=int
)
SITE_URL = config("SITE_URL", default="http://localhost:8000")

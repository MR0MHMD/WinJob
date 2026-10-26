import os
from pathlib import Path
from django.templatetags.static import static
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-284%)x7e&c@%q(gdi)j!74x++r+z24(@3+6(hziks__er5wh7r'

DEBUG = True

ALLOWED_HOSTS = []

INSTALLED_APPS = [
    'django_daisy',
    'django.contrib.admin',
    'django.contrib.humanize',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sitemaps',
    # packages
    'storages',
    'django_jalali',
    "django_resized",
    'django_iranian_payment.contrib.django',
    # apps
    'accounts.apps.AccountsConfig',
    "core.apps.CoreConfig",
    "advertisers.apps.AdvertisersConfig",
    "influencers.apps.InfluencersConfig",
    "campaigns.apps.CampaignsConfig",
    "windirect.common.apps.CommonConfig",
    "windirect.connections.apps.ConnectionsConfig",
    "windirect.comments.apps.CommentsConfig",
    "windirect.direct.apps.DirectConfig",
    "windirect.showcases.apps.ShowcasesConfig",
    "windirect.forms.apps.FormsConfig",
    "windirect.subscriptions.apps.SubscriptionsConfig",
    "blog.apps.BlogConfig",
    "content_team.apps.ContentTeamConfig",
    "notifications.apps.NotificationsConfig",
    "tickets.apps.TicketsConfig",
    "gamification.apps.GamificationConfig",
    "support.apps.SupportConfig",
    "payment.apps.PaymentConfig",
    "market.apps.MarketConfig",
    "django_cleanup.apps.CleanupConfig",
]

DAISY_SETTINGS = {
    # Branding
    'SITE_TITLE': 'پنل ادمین',
    'SITE_HEADER': 'ناحیه مدیریتی',
    'INDEX_TITLE': 'سلام به پنل مدیریتی سایت وینجاب خوش آمدید',
    'SITE_LOGO': '/static/finder/img/logo/logo.webp',

    'EXTRA_STYLES': ['/static/finder/css/them.min.css', '/static/finder/css/bootstrap-icons.css'],
    # 'EXTRA_SCRIPTS': ['static/finder/js/them.min.js'],
    'LOAD_FULL_STYLES': False,
    'SHOW_CHANGELIST_FILTER': True,
    'DONT_SUPPORT_ME': True,
    'SIDEBAR_FOOTNOTE': 'ساخته شده با عشق در 2026',

    'DEFAULT_THEME_DARK': True,
    'SHOW_THEME_SELECTOR': True,

    'APPS_REORDER': {
        'auth': {
            'icon': 'fa-solid fa-person-military-pointing',
            'name': 'احراز هویت',
            'hide': None,
            'divider_title': "Auth",
        },
        'core': {
            'icon': 'bi bi-cpu',
            'name': 'مرکز',
            'hide': None,
        },
        'advertisers': {
            'icon': 'bi bi-person-badge',
            'name': 'مشتریان',
            'hide': None,
        },
        'influencers': {
            'icon': 'bi bi-newspaper',
            'name': 'ناشران',
            'hide': None,
        },
        'campaigns': {
            'icon': 'bi bi-megaphone-fill',
            'name': 'کمپین ها',
            'hide': None,
        },
        'connections': {
            'icon': 'bi bi-instagram',
            'name': 'وین دایرکت | اتصالات',
            'hide': None,
        },
        'comments': {
            'icon': 'bi bi-chat-square-text',
            'name': 'وین دایرکت | کامنت هوشمند',
            'hide': None,
        },
        'direct': {
            'icon': 'bi bi-chat-dots-fill',
            'name': 'وین دایرکت | دایرکت هوشمند',
            'hide': None,
        },
        'showcases': {
            'icon': 'bi bi-grid',
            'name': 'وین دایرکت | ویترین ساز',
            'hide': None,
        },
        'forms': {
            'icon': 'bi bi-ui-checks',
            'name': 'وین دایرکت | فرم ساز',
            'hide': None,
        },
        'subscriptions': {
            'icon': 'bi bi-credit-card',
            'name': 'وین دایرکت | اشتراک ها',
            'hide': None,
        },
        'blog': {
            'icon': 'bi bi-journal-text',
            'name': 'بلاگ',
            'hide': None,
        },
        'accounts': {
            'icon': 'bi bi-people-fill',
            'name': 'کاربران',
            'hide': None,
        },
        'content_team': {
            'icon': 'bi bi-file-earmark-post-fill',
            'name': 'تولید محتوا',
            'hide': None,
        },
        'payment': {
            'icon': 'bi bi-cash',
            'name': 'مدیریت مالی',
            'hide': None,
        },
        'notifications': {
            'icon': 'bi bi-bell',
            'name': 'اعلان ها',
            'hide': None,
        }
        , 'tickets': {
            'icon': 'bi bi-ticket',
            'name': 'تیکت ها',
            'hide': None,
        }
        , 'gamification': {
            'icon': 'bi bi-star',
            'name': 'امتیاز ها',
            'hide': None,
        },
    },
}

# ========== درگاه پرداخت زرین پال ==========
ZARINPAL_MERCHANT_CODE = os.getenv('ZARINPAL_MERCHANT_CODE', 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')

PAYMENT_ENV = os.getenv('PAYMENT_ENV', 'development' if DEBUG else 'production').lower()
if PAYMENT_ENV not in ('development', 'production'):
    raise ValueError('PAYMENT_ENV باید development یا production باشد.')
PAYMENT_SANDBOX = PAYMENT_ENV == 'development'

IRANIAN_PAYMENT = {
    "sandbox": PAYMENT_SANDBOX,
    "currency": "toman",
    "gateways": {
        "zarinpal": {
            "merchant_id": ZARINPAL_MERCHANT_CODE,
            "sandbox": PAYMENT_SANDBOX,
        },
    },
}

LANGUAGES = [
    ('en', 'English'),
    ('fa', 'Farsi'),
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'support.utils.PlatformManagerAdminGuard',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = "WinJob.urls"

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'core.context_processors.platform_info',
                'core.context_processors.domain',
                'django.contrib.messages.context_processors.messages',
                'notifications.context_processors.unread_notifications',
                'support.context_processors.support_menu',
                'market.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'WinJob.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'fa-ir'

TIME_ZONE = 'Asia/Tehran'

USE_I18N = True
USE_TZ = True

BASE_URL = os.getenv("BASE_URL")

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

STATIC_ROOT = BASE_DIR / "staticfiles"

USE_THOUSAND_SEPARATOR = True
THOUSAND_SEPARATOR = ','
NUMBER_GROUPING = 3

DATE_FORMAT = 'Y/m/d'
DATETIME_FORMAT = 'Y/m/d | H:i:s'

AUTH_USER_MODEL = "accounts.CustomUser"

GHASEDAK_OTP_API = os.getenv("GHASEDAK_OTP_API")
GHASEDAK_OTP_TEMPLATE = "WinJobOTP"
GHASEDAK_RESET_PASSWORD_TEMPLATE = "WinJobResetPassword"

BALE_BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN")
if not BALE_BOT_TOKEN:
    raise ValueError("متغیر BALE_BOT_TOKEN در فایل .env تنظیم نشده است!")

# ========== تنظیمات Celery ==========r
CELERY_ENABLED = False

if CELERY_ENABLED:
    CELERY_BROKER_URL = os.environ.get('REDIS_URL', 'redis://127.0.0.1:6379/0')
    CELERY_RESULT_BACKEND = CELERY_BROKER_URL
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_TIMEZONE = TIME_ZONE
else:
    CELERY_BROKER_URL = None
    CELERY_RESULT_BACKEND = None

USE_N8N_VERIFICATION = False
N8N_VERIFICATION_WEBHOOK_URL = ""
N8N_CAMPAIGN_REPORT_WEBHOOK = ""
N8N_CALLBACK_SECRET = ""
N8N_API_TOKEN = ""

# AI
CHABOKAN_API_KEY = os.environ.get('CHABOKAN_API_KEY', '').strip()

# ==================== BoxAPI ====================
BOXAPI_API_KEY = os.environ.get("BOXAPI_API_KEY", "")
BOXAPI_BASE_URL = "https://api.sendbox.chat/api/v1"
BOXAPI_OAUTH_URL = "https://api.sendbox.chat/instagram-oauth"
BOXAPI_WEBHOOK_SECRET = os.environ.get("BOXAPI_WEBHOOK_SECRET", "")

# Minipay / VPOS
MINIPAY_BASE_URL = os.environ.get("MINIPAY_BASE_URL", "https://api.minipay.me/api/v1")
MINIPAY_BRANCH_ID = os.environ.get("MINIPAY_BRANCH_ID", "")
MINIPAY_USERNAME = os.environ.get("MINIPAY_USERNAME", "")
MINIPAY_PASSWORD = os.environ.get("MINIPAY_PASSWORD", "")
MINIPAY_API_KEY = os.environ.get("MINIPAY_API_KEY", "")
MINIPAY_TIMEOUT = 30

# ==================== تنظیمات استوریج (لوکال vs آروان) ====================

AWS_STORAGE_BUCKET_NAME = 'winjob'
AWS_S3_REGION_NAME = 'ir-central1'
AWS_S3_ENDPOINT_URL = 'https://s3.ir-central1.arvanstorage.ir'
AWS_S3_ADDRESSING_STYLE = 'virtual'
AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
AWS_QUERYSTRING_AUTH = False
AWS_DEFAULT_ACL = 'public-read'
AWS_S3_OBJECT_PARAMETERS = {'CacheControl': 'max-age=86400'}
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False

AWS_S3_CUSTOM_DOMAIN = f'{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.arvanstorage.ir'

if DEBUG:
    MEDIA_URL = '/media/'
    MEDIA_ROOT = BASE_DIR / 'media'

    SITE_URL = "http://localhost:8000"

    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

else:
    MEDIA_LOCATION = 'media'

    MEDIA_URL = f'https://{AWS_S3_CUSTOM_DOMAIN}/{MEDIA_LOCATION}/'
    MEDIA_ROOT = BASE_DIR / 'media'

    SITE_URL = "https://winjob.ir"

    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "location": MEDIA_LOCATION,
                "endpoint_url": AWS_S3_ENDPOINT_URL,
                "region_name": AWS_S3_REGION_NAME,
                "addressing_style": AWS_S3_ADDRESSING_STYLE,
                "default_acl": AWS_DEFAULT_ACL,
                "querystring_auth": AWS_QUERYSTRING_AUTH,
                "file_overwrite": AWS_S3_FILE_OVERWRITE,
                "object_parameters": AWS_S3_OBJECT_PARAMETERS,
                "signature_version": AWS_S3_SIGNATURE_VERSION,
            },
        },
        "staticfiles": {
            "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
        },
    }

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
    # packages
    'django_jalali',
    "django_resized",
    "django_cleanup",
    'django_iranian_payment.contrib.django',
    # apps
    'accounts.apps.AccountsConfig',
    "core.apps.CoreConfig",
    "advertisers.apps.AdvertisersConfig",
    "influencers.apps.InfluencersConfig",
    "campaigns.apps.CampaignsConfig",
    "blog.apps.BlogConfig",
    "content_team.apps.ContentTeamConfig",
    "notifications.apps.NotificationsConfig",
    "tickets.apps.TicketsConfig",
    "gamification.apps.GamificationConfig",
    "support.apps.SupportConfig",
    "payment.apps.PaymentConfig"
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
        ,'tickets': {
            'icon': 'bi bi-ticket',
            'name': 'تیکت ها',
            'hide': None,
        }
        ,'gamification': {
            'icon': 'bi bi-star',
            'name': 'امتیاز ها',
            'hide': None,
        },
    },
}

# ========== درگاه پرداخت زرین پال ==========
ZARINPAL_MERCHANT_CODE = os.getenv('ZARINPAL_MERCHANT_CODE', 'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx')

IRANIAN_PAYMENT = {
    "sandbox": True if ZARINPAL_MERCHANT_CODE == "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" else False,
    "currency": "toman",
    "gateways": {
        "zarinpal": {
            "merchant_id": ZARINPAL_MERCHANT_CODE,
            "sandbox": True if ZARINPAL_MERCHANT_CODE == "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx" else False,
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

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

GHASEDAK_OTP_API = os.getenv("GHASEDAK_OTP_API")
GHASEDAK_OTP_TEMPLATE = os.getenv('GHASEDAK_OTP_TEMPLATE')
BALE_BOT_TOKEN = os.environ.get("BALE_BOT_TOKEN")
if not BALE_BOT_TOKEN:
    raise ValueError("متغیر BALE_BOT_TOKEN در فایل .env تنظیم نشده است!")

SITE_URL = os.environ.get("SITE_URL", "https://winjob.chbkn.run")


# ========== تنظیمات Celery ==========
CELERY_ENABLED = os.environ.get('CELERY_ENABLED', 'False') == 'True'

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

USE_N8N_VERIFICATION = os.getenv('USE_N8N_VERIFICATION', 'False') == 'True'
N8N_VERIFICATION_WEBHOOK_URL = os.getenv('N8N_VERIFICATION_WEBHOOK_URL', '')
N8N_CAMPAIGN_REPORT_WEBHOOK = os.getenv("N8N_CAMPAIGN_REPORT_WEBHOOK")
N8N_CALLBACK_SECRET = os.getenv("N8N_CALLBACK_SECRET")

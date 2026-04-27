import os
from pathlib import Path
from django.templatetags.static import static
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-284%)x7e&c@%q(gdi)j!74x++r+z24(@3+6(hziks__er5wh7r'

DEBUG = True

ALLOWED_HOSTS = []

# Application definition

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
    # apps
    'accounts.apps.AccountsConfig',
    "core.apps.CoreConfig",
    "advertisers.apps.AdvertisersConfig",
    "influencers.apps.InfluencersConfig",
    "campaigns.apps.CampaignsConfig",
    "blog.apps.BlogConfig",
    "location.apps.LocationConfig",
    "plat_form.apps.PlatFormConfig",
    "content_team.apps.ContentTeamConfig",
    "notifications.apps.NotificationsConfig"
]

DAISY_SETTINGS = {
    # Branding
    'SITE_TITLE': 'پنل ادمین',
    'SITE_HEADER': 'ناحیه مدیریتی',
    'INDEX_TITLE': 'سلام به پنل مدیریتی سایت وینجاب خوش آمدید',
    'SITE_LOGO': '/static/finder/img/logo/Untitled03.png',


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
            'name': 'Authentication',
            'hide': None,
            'divider_title': "Auth",
        },
        'core': {
            'icon': 'bi bi-cpu',
            'name': 'هسته',
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
        'location': {
            'icon': 'bi bi-geo-alt-fill',
            'name': 'موقعیت',
            'hide': None,
        },
        'plat_form': {
            'icon': 'bi bi-window-dock',
            'name': 'سکو ها',
            'hide': None,
        },
        'content_team': {
            'icon': 'bi bi-file-earmark-post-fill',
            'name': 'تیم های تولید محتوا',
            'hide': None,
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

ROOT_URLCONF = 'WinJob.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'accounts.context_processors.auth_forms',
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

# ✅ این خط رو اضافه کن:
AUTH_USER_MODEL = 'accounts.CustomUser'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DJANGORESIZED_DEFAULT_SIZE = [800, 800]
DJANGORESIZED_DEFAULT_SCALE = 0.5
DJANGORESIZED_DEFAULT_QUALITY = 90
DJANGORESIZED_DEFAULT_KEEP_META = False
DJANGORESIZED_DEFAULT_FORCE_FORMAT = 'JPEG'
DJANGORESIZED_DEFAULT_FORMAT_EXTENSIONS = {'JPEG': ".jpg"}
DJANGORESIZED_DEFAULT_NORMALIZE_ROTATION = True

load_dotenv()

GHASEDAK_OTP_API = os.getenv("GHASEDAK_OTP_API")
GHASEDAK_OTP_TEMPLATE = os.getenv('GHASEDAK_OTP_TEMPLATE')

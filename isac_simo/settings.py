"""
Django settings for isac_simo project.

Generated by 'django-admin startproject' using Django 2.2.7.

For more information on this file, see
https://docs.djangoproject.com/en/2.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/2.2/ref/settings/
"""

import os
from datetime import timedelta
import dj_database_url
import environ
import sys
from isac_simo.database_settings import database_config

env = environ.Env()
env.read_env(env.str('ENV_PATH', '.env'))
from django.utils.translation import gettext_lazy as _

VERSION = '1.3.3'

TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/2.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = env('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DATABASE_URL = ''
IBM_API_KEY = ''
PRODUCTION = False

if env('DATABASE_URL'):
    DATABASE_URL = env('DATABASE_URL')

if env('IBM_API_KEY'):
    IBM_API_KEY = env('IBM_API_KEY')
else:
    print('NO IBM TOKEN')

if env('ENV') == 'production':
    PRODUCTION = True
    print('PRODUCTION')
else:
    print('LOCAL')

DEBUG = not PRODUCTION
TEMPLATE_DEBUG = DEBUG

GOOGLE_MAP_STREET_API = os.getenv('GOOGLE_MAP_STREET_API')
GOOGLE_MAP_API = os.getenv('GOOGLE_MAP_API')

ALLOWED_HOSTS = ['0.0.0.0', 'localhost', '127.0.0.1', 'buildchange.pythonanywhere.com', 'isac-simo.net',
                 'www.isac-simo.net', '149.81.165.216']

CORS_ALLOWED_ORIGINS = ['https://127.0.0.1', 'https://www.isac-simo.net',
                        'https://web.mondasolvo.net', 'https://www.mondasolvo.net', 'https://web.fulcrumapp.com', 'https://fulcrumapp.s3.amazonaws.com']

INTERNAL_IPS = (
    '127.0.0.1',
    'localhost'
)

APPEND_SLASH = True

# Application definition

DEFAULT_AUTO_FIELD='django.db.models.AutoField'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'corsheaders',
    'crispy_forms',
    'django_countries',
    'rest_framework',
    'rosetta',

    # Custom Apps
    'main',
    'projects',
    'api',
    'map',
    'crowdsource',

    # Load at last (To render custom error template)
    'honeypot',
]

AUTH_USER_MODEL = 'main.User'  # changes the built-in user model to ours

if PRODUCTION:
    SESSION_COOKIE_SECURE = True

MIDDLEWARE = [
    'api.middleware.MaintenanceMode',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # 'honeypot.middleware.HoneypotMiddleware', # NOT WORKING WELL WITH REST API - WE USE DECORATERS
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware'
]

ROOT_URLCONF = 'isac_simo.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'isac_simo.wsgi.application'

# Database
# https://docs.djangoproject.com/en/2.2/ref/settings/#databases

if env('DATABASE_URL'):
    DATABASES = {
        'default': dj_database_url.config(default=DATABASE_URL)
    }
else:
    DATABASES = {
        'default': database_config
    }

# Password validation
# https://docs.djangoproject.com/en/2.2/ref/settings/#auth-password-validators

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

# Internationalization
# https://docs.djangoproject.com/en/2.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_L10N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.2/howto/static-files/

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static_files')
STATICFILES_DIRS = [
    os.path.join(BASE_DIR, "static"),
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DOCS_URL = '/docs/'
DOCS_ROOT = os.path.join(BASE_DIR, 'docs')

CRISPY_TEMPLATE_PACK = 'bootstrap4'
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'

# API SETTINGS
DEFAULT_RENDERER_CLASSES = (
    'rest_framework.renderers.JSONRenderer',
)

if DEBUG:
    DEFAULT_RENDERER_CLASSES = DEFAULT_RENDERER_CLASSES + (
        'rest_framework.renderers.BrowsableAPIRenderer',
    )

# USE DUMMY CACHE FOR TESTING
if TESTING:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.dummy.DummyCache',
        }
    }

else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': os.getenv('CACHE_LOCATION', '/var/tmp/django_cache'),
            'TIMEOUT': 3600,
            'OPTIONS': {
                'MAX_ENTRIES': 5000
            }
        }
    }

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.BasicAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticatedOrReadOnly',
    ),
    'DEFAULT_RENDERER_CLASSES': DEFAULT_RENDERER_CLASSES,
    'TEST_REQUEST_DEFAULT_FORMAT': 'json'
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(days=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),
    'ROTATE_REFRESH_TOKENS': False,
    'BLACKLIST_AFTER_ROTATION': True,

    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUDIENCE': None,
    'ISSUER': None,

    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',

    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',

    'JTI_CLAIM': 'jti',

    'SLIDING_TOKEN_REFRESH_EXP_CLAIM': 'refresh_exp',
    'SLIDING_TOKEN_LIFETIME': timedelta(minutes=5),
    'SLIDING_TOKEN_REFRESH_LIFETIME': timedelta(days=1),
}

IBM_BUCKET_ENDPOINT = os.getenv('IBM_BUCKET_ENDPOINT', '')
IBM_BUCKET = os.getenv('IBM_BUCKET', '')
IBM_BUCKET_TOKEN = os.getenv('IBM_BUCKET_TOKEN', '')
IBM_BUCKET_CRN = os.getenv('IBM_BUCKET_CRN', '')
IBM_BUCKET_PUBLIC_ENDPOINT = os.getenv('IBM_BUCKET_PUBLIC_ENDPOINT', '')

LOCALE_PATHS = (
    os.path.join(BASE_DIR, "locale"),)
SYSLOG_PATHS = (
    os.path.join(BASE_DIR, "syslog"),)

LANGUAGES = [
    ('en', _('English')),
    ('es', _('Spanish')),
    ('fr', _('French ')),
    # ('hi', _('Hindi')),
]

HONEYPOT_FIELD_NAME = "phonenumber"

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'error_file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': 'syslog/errors.log',
            "formatter": "verbose",
        },
        'mail_admins': {
            'level': 'ERROR',
            'class': 'django.utils.log.AdminEmailHandler',
            "formatter": "verbose",
        }
    },
    'loggers': {
        'django': {
            'handlers': ['error_file', 'mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
    },
}
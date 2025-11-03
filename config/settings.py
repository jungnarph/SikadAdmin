"""
Django settings for bike_sharing_admin project.
"""

import os
import dj_database_url
from pathlib import Path
from decouple import config
import firebase_admin
from firebase_admin import credentials

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security Settings
SECRET_KEY = config('SECRET_KEY', default='django-insecure-please-change-in-production-12345')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1').split(',')

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third party
    'crispy_forms',
    'crispy_bootstrap5',
    
    # Local apps
    'apps.accounts',
    'apps.bikes',
    'apps.geofencing',
    'apps.customers',
    'apps.rides',
    'apps.payments',
    'apps.support',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'

# Database - PostgreSQL
if DEBUG :
    print("Using PostgreSQL Database in Local")
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME', default='bike_sharing_db'),
            'USER': config('DB_USER', default='postgres'),
            'PASSWORD': config('DB_PASSWORD', default='postgres'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432'),
        }
    }
else:
    print("Using PostgreSQL Database in Production")
    DATABASES = {
        'default': dj_database_url.parse(os.environ.get('DATABASE_URL'), conn_max_age=600),
    }

# Custom User Model
AUTH_USER_MODEL = 'accounts.AdminUser'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Manila'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Crispy Forms
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

# Session settings
SESSION_COOKIE_AGE = 3600  # 1 hour
SESSION_SAVE_EVERY_REQUEST = True

# Login URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'

# Firebase Configuration
FIREBASE_CREDENTIALS_PATH = config('FIREBASE_CREDENTIALS_PATH', default='')

if FIREBASE_CREDENTIALS_PATH and os.path.exists(FIREBASE_CREDENTIALS_PATH):
    try:
        cred = credentials.Certificate(FIREBASE_CREDENTIALS_PATH)
        firebase_admin.initialize_app(cred)
        print("✓ Firebase initialized successfully")
    except Exception as e:
        print(f"✗ Firebase initialization failed: {e}")
else:
    print("⚠ Firebase credentials not configured")

FIREBASE_API_KEY = config('FIREBASE_API_KEY', default='')
FIREBASE_AUTH_DOMAIN = config('FIREBASE_AUTH_DOMAIN', default='')
FIREBASE_PROJECT_ID = config('FIREBASE_PROJECT_ID', default='')
FIREBASE_DATABASE_URL = config('FIREBASE_DATABASE_URL', default='https://cit306-finalproject-default-rtdb.firebaseio.com/')

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# Email Backend Configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# SMTP Configuration
EMAIL_HOST = config('EMAIL_HOST', default='smtp.gmail.com')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='sikadservices@gmail.com')
EMAIL_SUBJECT_PREFIX = '[Sikad Admin] '
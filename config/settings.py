import os
import sys
from pathlib import Path

# Base directory: D:\...\employee_management
BASE_DIR = Path(__file__).resolve().parent.parent

# Add apps directory to sys.path so apps can be imported easily
sys.path.insert(0, str(BASE_DIR / 'apps'))

# Load environment variables from .env if present
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                k, v = line.split('=', 1)
                os.environ.setdefault(k.strip(), v.strip())

# PyMySQL initialization for native MySQL connectivity
try:
    import pymysql
    pymysql.install_as_MySQLdb()
except ImportError:
    pass

SECRET_KEY = os.getenv('SECRET_KEY', 'employee-management-pro-netcom-secret-key-2026')
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 'yes')

ALLOWED_HOSTS = ['*']

# CSRF Trusted Origins for remote, LAN, and Railway cloud access
csrf_origins = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if csrf_origins:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in csrf_origins.split(',') if origin.strip()]
else:
    CSRF_TRUSTED_ORIGINS = [
        'http://127.0.0.1:8000',
        'http://localhost:8000',
        'http://0.0.0.0:8000',
        'https://*.railway.app',
        'https://*.up.railway.app',
        'http://*.railway.app',
        'http://*.up.railway.app',
    ]

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Custom Core Modular Applications
    'apps.users',
    'apps.departments',
    'apps.employees',
    'apps.attendance',
    'apps.leave_management',
    'apps.payroll',
    'apps.dashboard',
    'apps.reports',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
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
                'apps.users.context_processors.company_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Database Configuration (Railway DATABASE_URL / MySQL with fallback to SQLite)
database_url = os.getenv('DATABASE_URL') or os.getenv('MYSQL_URL')
mysql_host = os.getenv('MYSQLHOST') or os.getenv('DB_HOST', '127.0.0.1')
mysql_user = os.getenv('MYSQLUSER') or os.getenv('DB_USER', 'root')
mysql_password = os.getenv('MYSQLPASSWORD') or os.getenv('DB_PASSWORD', 'root')
mysql_db = os.getenv('MYSQLDATABASE') or os.getenv('DB_NAME', 'employee_db')
mysql_port = os.getenv('MYSQLPORT') or os.getenv('DB_PORT', '3306')

use_mysql = os.getenv('USE_MYSQL', 'True').lower() in ('true', '1', 'yes')

if database_url:
    import dj_database_url
    DATABASES = {
        'default': dj_database_url.config(
            default=database_url,
            conn_max_age=600,
            ssl_require=False
        )
    }
elif use_mysql:
    # Test if MySQL port is accessible to gracefully fallback to SQLite if offline
    mysql_accessible = True
    try:
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.6)
        result = sock.connect_ex((mysql_host, int(mysql_port)))
        sock.close()
        if result != 0:
            mysql_accessible = False
    except Exception:
        mysql_accessible = False

    if mysql_accessible:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.mysql',
                'NAME': mysql_db,
                'USER': mysql_user,
                'PASSWORD': mysql_password,
                'HOST': mysql_host,
                'PORT': mysql_port,
                'OPTIONS': {
                    'charset': 'utf8mb4',
                    'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                }
            }
        }
    else:
        # Seamless zero-friction fallback to populated SQLite database
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'database' / 'employee_db.sqlite3',
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'database' / 'employee_db.sqlite3',
        }
    }

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Kolkata'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files (User documents, profile photos)
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Authentication URLs (Preserving exact login URL path)
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard:index'
LOGOUT_REDIRECT_URL = 'login'

# Logging configuration
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'application.log',
            'formatter': 'verbose',
        },
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}

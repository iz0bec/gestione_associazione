# ******************************************************
# * Progetto:    Gestione Associazione
# * Autore:      Bartolomeo Santoro aka IZ0BEC
# * Email:       info@iz0bec.info
# * Descrizione: Impostazioni Django. Tutti i valori dipendenti dall'installazione
# *              si leggono da variabili d'ambiente o dal file .env (vedi .env.example).
# * Licenza:     CC0 1.0 Universal (pubblico dominio)
# * SPDX-License-Identifier: CC0-1.0
# ******************************************************

from pathlib import Path

import environ
from django.utils.csp import CSP

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

APP_NOME = "Gestione Associazione"
APP_VERSIONE = "0.0.1-rc.11"
APP_AUTORE = "Bartolomeo Santoro aka IZ0BEC"
APP_EMAIL_AUTORE = "info@iz0bec.info"
APP_REPOSITORY = "https://mygitlab.iz0bec.info/sbart64/gestione_associazione"

# ------------------------------------------------------------------ base
DEBUG = env.bool("DEBUG", default=False)
SECRET_KEY = env("SECRET_KEY")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django.forms",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "axes",
    "django_htmx",
    "django_filters",
    "apps.core",
    "apps.accounts",
    "apps.anagrafica",
    "apps.soci",
    "apps.protocollo",
    "apps.organi",
    "apps.comunicazioni",
    "apps.tesoreria",
    "apps.patrimonio",
    "apps.documenti",
    "apps.calendario",
    "apps.migrazione",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.middleware.csp.ContentSecurityPolicyMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.core.middleware.ContestoRichiestaMiddleware",
    "apps.accounts.middleware.ObblighiAccessoMiddleware",
    # django-axes deve restare l'ultimo
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.template.context_processors.csp",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.applicazione",
            ],
        },
    },
]
FORM_RENDERER = "apps.core.forms.RendererModuli"

# ------------------------------------------------------------------ database
DATABASES = {"default": env.db("DATABASE_URL")}
DATABASES["default"]["ATOMIC_REQUESTS"] = False
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=60)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ------------------------------------------------------------------ autenticazione
AUTH_USER_MODEL = "accounts.Utente"
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "account_login"
LOGIN_REDIRECT_URL = "core:cruscotto"
LOGOUT_REDIRECT_URL = "account_login"

# allauth: niente registrazione libera, gli account li crea l'amministratore
ACCOUNT_ADAPTER = "apps.accounts.adapter.AdapterAccount"
ACCOUNT_LOGIN_METHODS = {"username", "email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "username*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "none"
ACCOUNT_LOGOUT_ON_PASSWORD_CHANGE = True
ACCOUNT_SESSION_REMEMBER = False
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_TOTP_ISSUER = env("MFA_TOTP_ISSUER", default=APP_NOME)
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = DEBUG

# django-axes: blocco dopo 5 tentativi falliti per 15 minuti (utente + IP)
AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=5)
AXES_COOLOFF_TIME = env.float("AXES_COOLOFF_ORE", default=0.25)
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_LOCKOUT_TEMPLATE = "errori/bloccato.html"
# dietro reverse proxy: PROXY_COUNT proxy in catena; PROXY_FIDATI = IP o reti da cui accettare
# X-Forwarded-For (es. 192.168.0.26,192.168.0.34); vuoto = da chiunque
PROXY_COUNT = env.int("PROXY_COUNT", default=0)
PROXY_FIDATI = env.list("PROXY_FIDATI", default=[])
AXES_CLIENT_IP_CALLABLE = "apps.core.rete.ip_client"

# ------------------------------------------------------------------ lingua e orari
LANGUAGE_CODE = "it"
LOCALE_PATHS = [BASE_DIR / "locale"]  # traduzioni mancanti in Django (es. scelta vuota)
LANGUAGES = [("it", "Italiano")]
TIME_ZONE = "Europe/Rome"
USE_I18N = True
USE_TZ = True

# ------------------------------------------------------------------ file
STATIC_URL = "static/"
STATIC_ROOT = env.path("STATIC_ROOT", default=BASE_DIR / "var" / "static")
STATICFILES_DIRS = [BASE_DIR / "static"]
# MEDIA_ROOT NON è servita dal web server: gli allegati passano sempre da viste con permessi
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "var" / "media")
MEDIA_URL = "/non-servito/"

# Backup completi (database + file): cartella, backup automatico notturno e quanti conservarne
BACKUP_ROOT = env.path("BACKUP_ROOT", default=BASE_DIR / "var" / "backup")
BACKUP_AUTOMATICO = env.bool("BACKUP_AUTOMATICO", default=True)
BACKUP_ORA = env.int("BACKUP_ORA", default=2)
BACKUP_CONSERVA = env.int("BACKUP_CONSERVA", default=14)
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": (
            "apps.core.statici.StaticiSviluppo"
            if DEBUG
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
    },
}
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_PERMISSIONS = 0o640
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o750
DATA_UPLOAD_MAX_NUMBER_FILES = 20

# Chiavi Fernet (separate da virgola, la prima cifra) per i segreti nel database, es. password IMAP
CHIAVE_CIFRATURA = env("CHIAVE_CIFRATURA", default="")

# Indirizzo pubblico dell'applicazione (es. https://gestione.miassociazione.it),
# usato nei QR stampati
URL_PUBBLICO = env("URL_PUBBLICO", default="").rstrip("/")

# Comunicazioni: messaggi spediti a ogni giro della coda (il pianificatore gira ogni minuto)
COMUNICAZIONI_LOTTO = env.int("COMUNICAZIONI_LOTTO", default=30)

# Protocollo: dimensione massima di un allegato ed estensioni ammesse
PROTOCOLLO_ALLEGATO_MAX_MB = env.int("PROTOCOLLO_ALLEGATO_MAX_MB", default=25)
PROTOCOLLO_ESTENSIONI = env.list(
    "PROTOCOLLO_ESTENSIONI",
    default=[
        "pdf", "p7m", "xml", "eml", "txt", "rtf", "odt", "ods", "odp", "doc", "docx", "xls",
        "xlsx", "ppt", "pptx", "csv", "jpg", "jpeg", "png", "gif", "webp", "tif", "tiff", "zip",
    ],
)  # fmt: skip

# ------------------------------------------------------------------ email
# Django 6.1: configurazione con MAILERS (le vecchie EMAIL_* sono deprecate)
_EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
_EMAIL_OPZIONI = {}
if _EMAIL_BACKEND.endswith("smtp.EmailBackend"):
    _EMAIL_OPZIONI = {
        "host": env("EMAIL_HOST", default="localhost"),
        "port": env.int("EMAIL_PORT", default=587),
        "username": env("EMAIL_HOST_USER", default=""),
        "password": env("EMAIL_HOST_PASSWORD", default=""),
        "use_tls": env.bool("EMAIL_USE_TLS", default=True),
        "use_ssl": env.bool("EMAIL_USE_SSL", default=False),
        "timeout": env.int("EMAIL_TIMEOUT", default=30),
    }
MAILERS = {"default": {"BACKEND": _EMAIL_BACKEND, "OPTIONS": _EMAIL_OPZIONI}}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@localhost")
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# ------------------------------------------------------------------ sicurezza HTTP
# HTTPS=true quando l'app è raggiungibile solo via HTTPS (diretto o tramite reverse proxy)
HTTPS = env.bool("HTTPS", default=False)
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SECURE_SSL_REDIRECT = HTTPS and env.bool("SECURE_SSL_REDIRECT", default=False)
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0) if HTTPS else 0
if PROXY_COUNT > 0:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = env.int("SESSION_DURATA_SECONDI", default=8 * 3600)
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
# i browser la ignorano (con un avviso) sulle origini non HTTPS
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin" if HTTPS else None

# Content Security Policy: solo risorse locali, script inline solo con nonce
SECURE_CSP = {
    "default-src": [CSP.SELF],
    "script-src": [CSP.SELF, CSP.NONCE],
    "style-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "font-src": [CSP.SELF],
    "connect-src": [CSP.SELF],
    "form-action": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
    "base-uri": [CSP.NONE],
    "object-src": [CSP.NONE],
}

# ------------------------------------------------------------------ log
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"semplice": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "semplice"}},
    "root": {"handlers": ["console"], "level": env("LOG_LEVEL", default="INFO")},
    "loggers": {
        "axes": {"level": "WARNING"},
        "weasyprint": {"level": "WARNING"},
        "fontTools": {"level": "WARNING"},
    },
}

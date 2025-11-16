from .base import *

DEBUG = False

GLOBAL_FCM_TOPIC_NAME = "Paycore_global"

# Production Performance Optimizations
# Enable database connection pooling (critical for performance)
DATABASES['default']['CONN_MAX_AGE'] = 600  # Keep connections alive for 10 minutes
DATABASES['default']['CONN_HEALTH_CHECKS'] = True  # Validate connections before use

# Increase statement timeout for production
DATABASES['default']['OPTIONS']['options'] = '-c statement_timeout=60000'  # 60 seconds

# Add GZip compression middleware for faster response times
MIDDLEWARE.insert(2, 'django.middleware.gzip.GZipMiddleware')  # Insert after SecurityMiddleware

# Cache configuration optimizations
CACHES['default']['TIMEOUT'] = 600  # Increase default cache timeout to 10 minutes
CACHES['default']['OPTIONS']['CONNECTION_POOL_CLASS_KWARGS']['max_connections'] = 100  # More Redis connections

CELERY_BROKER_USE_SSL = True
CELERY_SSL_KEYFILE = ""
CELERY_SSL_CERTFILE = ""
CELERY_SSL_CA_CERTS = ""

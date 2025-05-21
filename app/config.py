import os
from datetime import timedelta

class Config:
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY', 'your-secret-key-here')
    SESSION_TYPE = 'filesystem'
    WTF_CSRF_ENABLED = True
    WTF_CSRF_TIME_LIMIT = None
    
    # Database settings
    DB_CONFIG = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'user': os.environ.get('DB_USER', 'root'),
        'password': os.environ.get('DB_PASSWORD', 'newpass123'),
        'database': os.environ.get('DB_NAME', 'medical_shop'),
        'port': int(os.environ.get('DB_PORT', 3306)),
        'raise_on_warnings': True,
        'autocommit': True,
        'pool_name': 'pharmacy_pool',
        'pool_size': 5
    }
    
    # Cache settings
    CACHE_TYPE = 'simple'
    CACHE_DEFAULT_TIMEOUT = 300
    
    # Rate limiting
    RATELIMIT_DEFAULT = "200 per day"
    RATELIMIT_STORAGE_URL = "memory://"
    
    # Session settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=1)
    
    # Logging settings
    LOG_FILE = 'app.log'
    LOG_LEVEL = 'DEBUG'
    LOG_FORMAT = '%(asctime)s - %(levelname)s - %(message)s'
    LOG_MAX_BYTES = 10000
    LOG_BACKUP_COUNT = 3

# SMTP config for password reset
SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT = int(os.environ.get('SMTP_PORT', 465))
SMTP_USER = os.environ.get('SMTP_USER', 'sridhar@shanmugha.edu.in')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', 'epmh ifsi ltrj tonj') 
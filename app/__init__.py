import os
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, render_template
from flask_wtf.csrf import CSRFProtect
from flask_caching import Cache
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from .config import Config
from .models.database import init_db

# Initialize Flask extensions
csrf = CSRFProtect()
cache = Cache()
limiter = Limiter(key_func=get_remote_address)

def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Initialize extensions
    csrf.init_app(app)
    cache.init_app(app)
    limiter.init_app(app)
    
    # Configure logging
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler(
        app.config['LOG_FILE'],
        maxBytes=app.config['LOG_MAX_BYTES'],
        backupCount=app.config['LOG_BACKUP_COUNT']
    )
    file_handler.setFormatter(logging.Formatter(app.config['LOG_FORMAT']))
    file_handler.setLevel(app.config['LOG_LEVEL'])
    app.logger.addHandler(file_handler)
    app.logger.setLevel(app.config['LOG_LEVEL'])
    
    # Initialize database
    with app.app_context():
        init_db()
    
    # Register blueprints
    from .routes.auth import auth
    from .routes.main import main
    from .routes.admin import admin
    from .routes.inventory import inventory
    from .routes.billing import billing
    
    app.register_blueprint(auth, url_prefix='/auth')
    app.register_blueprint(main, url_prefix='/')
    app.register_blueprint(admin, url_prefix='/admin')
    app.register_blueprint(inventory, url_prefix='/inventory')
    app.register_blueprint(billing, url_prefix='/billing')
    
    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return render_template('errors/500.html'), 500
    
    @app.errorhandler(429)
    def ratelimit_handler(error):
        return render_template('errors/429.html'), 429
    
    return app 
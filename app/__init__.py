import os
from flask import Flask
from .models import db

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.sqlite'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    with app.app_context():
        db.create_all()

    from .billing import billing_bp
    from .inventory import inventory_bp
    app.register_blueprint(billing_bp)
    app.register_blueprint(inventory_bp)

    return app

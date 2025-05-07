import os
from flask import Flask

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev')
    app.config['DATABASE'] = os.path.join(app.root_path, 'data.sqlite')

    from .billing import billing_bp
    from .inventory import inventory_bp

    app.register_blueprint(billing_bp)
    app.register_blueprint(inventory_bp)

    @app.route("/")
    def index():
        return "<h1>✅ Medical Shop App is Running</h1><p>Use /billing or /inventory</p>"

    return app

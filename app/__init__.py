import os
from flask import Flask, redirect, url_for

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
        return redirect(url_for("billing_bp.billing"))

    return app

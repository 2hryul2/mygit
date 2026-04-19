from flask import Flask, jsonify

from .auth import load_users
from .config import load_config
from .routes.smart_http import smart_http


def create_app() -> Flask:
    cfg = load_config()
    app = Flask(__name__)
    app.config["MYGIT"] = cfg
    app.config["MYGIT_USERS"] = load_users(cfg.auth_file)

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok")

    app.register_blueprint(smart_http)

    return app

import os

from flask import Flask

from labhive.config import config_map
from flask_cors import CORS

from labhive.extensions import db, jwt, ma, migrate


def create_app(env: str | None = None) -> Flask:
    if env is None:
        env = os.environ.get("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config_map[env])

    # Extensions
    _cors_origins = os.environ.get("CORS_ORIGINS", "http://localhost:4200").split(",")
    CORS(app, origins=_cors_origins)
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    ma.init_app(app)

    # Import models so Flask-Migrate detects them
    with app.app_context():
        from labhive import models  # noqa: F401

    # Error handlers
    from labhive.utils.errors import register_error_handlers
    register_error_handlers(app)

    # Blueprints
    from labhive.routes import register_blueprints
    register_blueprints(app)

    return app

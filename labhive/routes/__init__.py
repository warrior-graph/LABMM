from flask import Flask

from labhive.routes.activities import bp as activities_bp
from labhive.routes.auth import bp as auth_bp
from labhive.routes.dashboard import bp as dashboard_bp
from labhive.routes.inventory import bp as inventory_bp
from labhive.routes.laboratories import bp as labs_bp
from labhive.routes.members import bp as members_bp
from labhive.routes.projects import bp as projects_bp
from labhive.routes.research import bp as research_bp
from labhive.routes.roles import bp as roles_bp


def register_blueprints(app: Flask) -> None:
    app.register_blueprint(auth_bp)
    app.register_blueprint(labs_bp)
    app.register_blueprint(members_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(research_bp)
    app.register_blueprint(activities_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(roles_bp)
    app.register_blueprint(dashboard_bp)

    if app.debug:
        from labhive.routes.debug import bp as debug_bp

        app.register_blueprint(debug_bp)

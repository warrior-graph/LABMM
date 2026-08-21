import subprocess

from flask import Blueprint, jsonify

from labhive.extensions import db

bp = Blueprint("debug", __name__, url_prefix="/debug")


@bp.post("/reset-db")
def reset_db():
    result = subprocess.run(
        ["./reset_db.sh"],
        capture_output=True,
        text=True,
        cwd="/app",
    )
    if result.returncode != 0:
        return jsonify(ok=False, stderr=result.stderr), 500
    # Drop all pooled connections so Flask reconnects to the fresh database.
    db.engine.dispose()
    return jsonify(ok=True, stdout=result.stdout), 200

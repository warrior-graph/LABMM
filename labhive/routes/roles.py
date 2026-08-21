import re

from flask import Blueprint, abort, jsonify, request

from labhive.extensions import db
from labhive.models.lab_membership import LabMembership
from labhive.models.role import Role
from labhive.schemas.role_schema import role_schema, roles_schema
from labhive.utils.decorators import require_super_admin
from flask_jwt_extended import jwt_required

bp = Blueprint("roles", __name__)


@bp.get("/roles")
@jwt_required()
def list_roles():
    roles = Role.query.order_by(Role.level, Role.name).all()
    return jsonify(roles_schema.dump(roles)), 200


@bp.post("/roles")
@require_super_admin
def create_role():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    level = data.get("level")

    if not name or level is None:
        return jsonify(error="name and level are required."), 422
    if not isinstance(level, int) or level < 0 or level > 4:
        return jsonify(error="level must be an integer between 0 and 4."), 422

    # Derive a key from the name (snake_case, alphanumeric + underscore)
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    if not key:
        return jsonify(error="name produces an invalid key."), 422

    if Role.query.filter_by(key=key).first():
        return jsonify(error="A role with this key already exists."), 409

    role = Role(key=key, name=name, level=int(level), is_system=False)
    db.session.add(role)
    db.session.commit()
    return jsonify(role_schema.dump(role)), 201


@bp.delete("/roles/<string:key>")
@require_super_admin
def delete_role(key: str):
    role = Role.query.filter_by(key=key).first()
    if not role:
        abort(404, "Role not found.")
    if role.is_system:
        abort(403, "System roles cannot be deleted.")

    in_use = LabMembership.query.filter_by(role=key).first()
    if in_use:
        abort(409, "Cannot delete a role that is currently assigned to a member.")

    db.session.delete(role)
    db.session.commit()
    return "", 204

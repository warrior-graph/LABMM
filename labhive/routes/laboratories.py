from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.lab_membership import LabMembership, LabRole
from labhive.models.laboratory import Laboratory
from labhive.schemas.laboratory_schema import (
    laboratories_schema,
    laboratory_schema,
)
from labhive.utils.decorators import require_professor_or_super_admin, require_super_admin

bp = Blueprint("laboratories", __name__, url_prefix="/labs")


@bp.get("/directory")
def labs_directory():
    """Public endpoint — returns all lab ids and names for the self-registration form."""
    labs = Laboratory.query.order_by(Laboratory.name).all()
    return jsonify([{"id": lab.id, "name": lab.name} for lab in labs]), 200


@bp.get("")
@jwt_required()
def list_labs():
    from flask_jwt_extended import get_jwt, get_jwt_identity

    claims = get_jwt()
    if claims.get("is_super_admin"):
        labs = Laboratory.query.all()
    else:
        member_id = int(get_jwt_identity())
        from labhive.models.lab_membership import LabMembership
        memberships = LabMembership.query.filter_by(member_id=member_id).all()
        lab_ids = [m.lab_id for m in memberships]
        labs = Laboratory.query.filter(Laboratory.id.in_(lab_ids)).all()
    return jsonify(laboratories_schema.dump(labs)), 200


@bp.post("")
@require_professor_or_super_admin
def create_lab():
    data = request.get_json(silent=True) or {}
    try:
        lab = laboratory_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    db.session.add(lab)
    db.session.flush()  # get lab.id before commit

    # Auto-add the creator as Lab Coordinator — but skip for super-admins,
    # who are above all lab roles and manage labs without a membership.
    claims = get_jwt()
    if not claims.get("is_super_admin"):
        creator_id = int(get_jwt_identity())
        membership = LabMembership(
            member_id=creator_id,
            lab_id=lab.id,
            roles=[LabRole.lab_coordinator],
        )
        db.session.add(membership)

    db.session.commit()
    return jsonify(laboratory_schema.dump(lab)), 201


@bp.get("/<int:lab_id>")
@jwt_required()
def get_lab(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    return jsonify(laboratory_schema.dump(lab)), 200


@bp.put("/<int:lab_id>")
@require_super_admin
def update_lab(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    data = request.get_json(silent=True) or {}
    try:
        lab = laboratory_schema.load(data, instance=lab, partial=True)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    db.session.commit()
    return jsonify(laboratory_schema.dump(lab)), 200


@bp.delete("/<int:lab_id>")
@require_super_admin
def delete_lab(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    db.session.delete(lab)
    db.session.commit()
    return "", 204


@bp.post("/<int:lab_id>/deactivate")
@require_super_admin
def deactivate_lab(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    lab.is_active = False
    db.session.commit()
    return jsonify(laboratory_schema.dump(lab)), 200


@bp.post("/<int:lab_id>/activate")
@require_super_admin
def activate_lab(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    lab.is_active = True
    db.session.commit()
    return jsonify(laboratory_schema.dump(lab)), 200

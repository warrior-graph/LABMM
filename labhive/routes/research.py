from flask import Blueprint, abort, jsonify, request
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.lab_membership import LabMembership, LabRole
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.research import Research
from labhive.schemas.research_schema import (
    research_input_schema,
    research_schema,
    researches_schema,
)
from labhive.utils.decorators import require_lab_member, require_lab_role

bp = Blueprint("research", __name__)


@bp.get("/labs/<int:lab_id>/research")
@require_lab_member
def list_research(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    return jsonify(researches_schema.dump(lab.research_groups)), 200


@bp.post("/labs/<int:lab_id>/research")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def create_research(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    data = request.get_json(silent=True) or {}

    # Validate manager_id belongs to the lab if provided
    manager_id = data.get("manager_id")
    if manager_id is not None:
        mgr_membership = LabMembership.query.filter_by(
            member_id=manager_id, lab_id=lab_id
        ).first()
        if not mgr_membership:
            return jsonify(error="Research manager must be a member of this laboratory."), 422

    try:
        group = research_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    group.lab_id = lab_id
    db.session.add(group)
    db.session.commit()
    return jsonify(research_schema.dump(group)), 201


@bp.get("/labs/<int:lab_id>/research/<int:research_id>")
@require_lab_member
def get_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    return jsonify(research_schema.dump(group)), 200


@bp.put("/labs/<int:lab_id>/research/<int:research_id>")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def update_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    data = request.get_json(silent=True) or {}

    # Validate manager_id belongs to the lab if provided
    manager_id = data.get("manager_id")
    if manager_id is not None:
        mgr_membership = LabMembership.query.filter_by(
            member_id=manager_id, lab_id=lab_id
        ).first()
        if not mgr_membership:
            return jsonify(error="Research manager must be a member of this laboratory."), 422

    try:
        group = research_input_schema.load(data, instance=group, partial=True)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    db.session.commit()
    return jsonify(research_schema.dump(group)), 200


@bp.delete("/labs/<int:lab_id>/research/<int:research_id>")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def delete_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    db.session.delete(group)
    db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/research/<int:research_id>/members")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def add_member_to_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    if not member_id:
        return jsonify(error="'member_id' is required."), 422
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member in group.members:
        return jsonify(error="Member already in this research group."), 409
    group.members.append(member)
    db.session.commit()
    return jsonify(research_schema.dump(group)), 200


@bp.delete("/labs/<int:lab_id>/research/<int:research_id>/members/<int:member_id>")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def remove_member_from_research(lab_id: int, research_id: int, member_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    member = db.session.get(Member, member_id)
    if not member or member not in group.members:
        abort(404, "Member not found in this research group.")
    group.members.remove(member)
    db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/research/<int:research_id>/deactivate")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def deactivate_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    group.is_active = False
    db.session.commit()
    return jsonify(research_schema.dump(group)), 200


@bp.post("/labs/<int:lab_id>/research/<int:research_id>/activate")
@require_lab_role(LabRole.chief_scientist, LabRole.lab_coordinator)
def activate_research(lab_id: int, research_id: int):
    group = Research.query.filter_by(id=research_id, lab_id=lab_id).first()
    if not group:
        abort(404, "Research group not found.")
    group.is_active = True
    db.session.commit()
    return jsonify(research_schema.dump(group)), 200

from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.activity import Activity, ActivityStatus
from labhive.models.lab_membership import LabRole, MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.schemas.activity_schema import (
    activities_schema,
    activity_input_schema,
    activity_schema,
)
from labhive.utils.decorators import require_lab_role

bp = Blueprint("activities", __name__)


def _resolve_members(ids, field_name: str) -> list[Member]:
    """Resolve a list of member ids; abort with 422 if any id is unknown or duplicated."""
    if not isinstance(ids, list):
        abort(422, f"{field_name} must be a list of member IDs.")
    unique = set(ids)
    if len(ids) != len(unique):
        abort(422, f"{field_name} contains duplicate member IDs.")
    members = Member.query.filter(Member.id.in_(ids)).all()
    if len(members) != len(unique):
        abort(422, f"One or more members in {field_name} are invalid.")
    return members


@bp.get("/labs/<int:lab_id>/activities")
def list_activities(lab_id: int):
    """Public endpoint — no token required.
    Pass ?completed_only=true to return only completed activities.
    """
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    completed_only = request.args.get("completed_only", "").lower() in (
        "1",
        "true",
        "yes",
    )
    query = Activity.query.filter_by(lab_id=lab_id)
    if completed_only:
        query = query.filter_by(status=ActivityStatus.completed)

    return jsonify(activities_schema.dump(query.all())), 200


@bp.get("/labs/<int:lab_id>/activities/<int:activity_id>")
def get_activity(lab_id: int, activity_id: int):
    """Public endpoint — no token required."""
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    return jsonify(activity_schema.dump(activity)), 200


@bp.post("/labs/<int:lab_id>/activities")
@require_lab_role(
    LabRole.lab_coordinator,
    LabRole.chief_scientist,
    LabRole.researcher,
    LabRole.research_fellow,
)
def create_activity(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    data = request.get_json(silent=True) or {}
    in_charge_ids = data.pop("in_charge", [])
    participant_ids = data.pop("participants", [])
    try:
        activity = activity_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    activity.lab_id = lab_id
    if in_charge_ids:
        activity.in_charge = _resolve_members(in_charge_ids, "in_charge")
    if participant_ids:
        activity.participants = _resolve_members(participant_ids, "participants")
    db.session.add(activity)
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 201


@bp.put("/labs/<int:lab_id>/activities/<int:activity_id>")
@require_lab_role(
    LabRole.lab_coordinator,
    LabRole.chief_scientist,
    LabRole.researcher,
    LabRole.research_fellow,
)
def update_activity(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    data = request.get_json(silent=True) or {}
    in_charge_ids = data.pop("in_charge", None)
    participant_ids = data.pop("participants", None)
    try:
        activity = activity_input_schema.load(data, instance=activity, partial=True)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    if in_charge_ids is not None:
        activity.in_charge = _resolve_members(in_charge_ids, "in_charge")
    if participant_ids is not None:
        activity.participants = _resolve_members(participant_ids, "participants")
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.post("/labs/<int:lab_id>/activities/<int:activity_id>/review")
@require_lab_role(*MANAGER_ROLES)
def review_activity(lab_id: int, activity_id: int):
    """Coordinator/manager decision on an activity under review: accepted or rejected."""
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    data = request.get_json(silent=True) or {}
    decision = data.get("decision")
    if decision not in ("accepted", "rejected"):
        abort(422, "decision must be 'accepted' or 'rejected'.")
    if activity.status != ActivityStatus.under_review:
        abort(409, "Only activities under review can be reviewed.")
    activity.status = ActivityStatus(decision)
    if decision == "accepted":
        activity.completed_at = datetime.now(timezone.utc).date()
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.delete("/labs/<int:lab_id>/activities/<int:activity_id>")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist)
def delete_activity(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    db.session.delete(activity)
    db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/activities/<int:activity_id>/deactivate")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist)
def deactivate_activity(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    activity.is_active = False
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.post("/labs/<int:lab_id>/activities/<int:activity_id>/activate")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist)
def activate_activity(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    activity.is_active = True
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.post("/labs/<int:lab_id>/activities/<int:activity_id>/participants")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist, LabRole.researcher)
def add_participant(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member in activity.participants:
        return jsonify(error="Member already in this activity."), 409
    activity.participants.append(member)
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.delete("/labs/<int:lab_id>/activities/<int:activity_id>/participants/<int:member_id>")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist, LabRole.researcher)
def remove_participant(lab_id: int, activity_id: int, member_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    member = db.session.get(Member, member_id)
    if member in activity.participants:
        activity.participants.remove(member)
        db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/activities/<int:activity_id>/in_charge")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist)
def add_in_charge(lab_id: int, activity_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member in activity.in_charge:
        return jsonify(error="Member already in charge of this activity."), 409
    activity.in_charge.append(member)
    db.session.commit()
    return jsonify(activity_schema.dump(activity)), 200


@bp.delete("/labs/<int:lab_id>/activities/<int:activity_id>/in_charge/<int:member_id>")
@require_lab_role(LabRole.lab_coordinator, LabRole.chief_scientist)
def remove_in_charge(lab_id: int, activity_id: int, member_id: int):
    activity = Activity.query.filter_by(id=activity_id, lab_id=lab_id).first()
    if not activity:
        abort(404, "Activity not found.")
    member = db.session.get(Member, member_id)
    if member in activity.in_charge:
        activity.in_charge.remove(member)
        db.session.commit()
    return "", 204

"""Calendar events — activities (deadline) and projects (end_date), role-aware."""
import re

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from labhive.models.activity import Activity
from labhive.models.lab_membership import LabMembership, MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.project import Project

bp = Blueprint("calendar", __name__, url_prefix="/calendar")

_MONTH_RE = re.compile(r"^\d{4}-\d{2}$")


def _managed_lab_ids(claims: dict, member_id: int) -> list[int]:
    if claims.get("is_super_admin"):
        return [lab.id for lab in Laboratory.query.all()]
    return [
        ms.lab_id
        for ms in LabMembership.query.filter_by(member_id=member_id).all()
        if set(MANAGER_ROLES) & set(ms.roles or [])
    ]


@bp.get("")
@jwt_required()
def calendar_events():
    """Events with dates in scope: managers see managed labs (or ?lab_id=), members see their own.

    Optional ?month=YYYY-MM filters events whose date falls inside that month.
    """
    claims = get_jwt()
    member_id = int(get_jwt_identity())

    month = request.args.get("month")
    if month is not None and not _MONTH_RE.match(month):
        abort(422, "month must use YYYY-MM format.")

    lab_id = request.args.get("lab_id", type=int)

    if claims.get("is_super_admin"):
        lab_ids = (
            [lab_id] if lab_id else [lab.id for lab in Laboratory.query.all()]
        )
        activity_query = Activity.query.filter(Activity.lab_id.in_(lab_ids))
        project_query = Project.query.filter(Project.lab_id.in_(lab_ids))
    else:
        memberships = LabMembership.query.filter_by(member_id=member_id).all()
        if any(set(MANAGER_ROLES) & set(ms.roles or []) for ms in memberships):
            lab_ids = [ms.lab_id for ms in memberships if set(MANAGER_ROLES) & set(ms.roles or [])]
            if lab_id is not None:
                lab_ids = [lid for lid in lab_ids if lid == lab_id]
            if not lab_ids:
                return jsonify([]), 200
            activity_query = Activity.query.filter(Activity.lab_id.in_(lab_ids))
            project_query = Project.query.filter(Project.lab_id.in_(lab_ids))
        else:
            # Regular member — only their own activities/projects
            activity_query = Activity.query.filter(
                (Activity.participants.any(Member.id == member_id))
                | (Activity.in_charge.any(Member.id == member_id))
            )
            project_query = Project.query.filter(Project.members.any(Member.id == member_id))

    events: list[dict] = []

    for a in activity_query.filter(Activity.deadline.isnot(None)).all():
        if month and not a.deadline.isoformat().startswith(month):
            continue
        events.append(
            {
                "type": "activity",
                "id": a.id,
                "title": a.title,
                "lab_id": a.lab_id,
                "lab_name": a.laboratory.name if a.laboratory else None,
                "status": a.status.value,
                "date": a.deadline.isoformat(),
            }
        )

    for p in project_query.filter(Project.end_date.isnot(None)).all():
        if month and not p.end_date.isoformat().startswith(month):
            continue
        events.append(
            {
                "type": "project",
                "id": p.id,
                "title": p.name,
                "lab_id": p.lab_id,
                "lab_name": p.laboratory.name if p.laboratory else None,
                "status": p.status.value,
                "date": p.end_date.isoformat(),
            }
        )

    events.sort(key=lambda e: (e["date"], e["type"], e["title"]))
    return jsonify(events), 200

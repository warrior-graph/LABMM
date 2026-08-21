from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from labhive.extensions import db
from labhive.models.activity import Activity, ActivityStatus
from labhive.models.inventory import InventoryItem
from labhive.models.lab_membership import LabMembership, LabRole, MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.project import Project, ProjectStatus

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


def _is_manager(claims: dict, member_id: int) -> bool:
    """Super-admins manage every lab; others manage labs where they hold a manager role."""
    if claims.get("is_super_admin"):
        return True
    memberships = LabMembership.query.filter_by(member_id=member_id).all()
    return any(set(MANAGER_ROLES) & set(ms.roles or []) for ms in memberships)


def _managed_lab_ids(claims: dict, member_id: int) -> list[int]:
    """Labs in scope for manager-level fields."""
    if claims.get("is_super_admin"):
        return [lab.id for lab in Laboratory.query.all()]
    memberships = LabMembership.query.filter_by(member_id=member_id).all()
    return [
        ms.lab_id
        for ms in memberships
        if set(MANAGER_ROLES) & set(ms.roles or [])
    ]


def _pending_members(claims: dict, member_id: int) -> list[Member]:
    """Mirror the /members/pending visibility rule (super-admin or professor with lab_coordinator)."""
    if claims.get("is_super_admin"):
        return Member.query.filter_by(is_approved=False).all()
    if claims.get("is_professor"):
        ceo_lab_ids = [
            ms.lab_id
            for ms in LabMembership.query.filter_by(member_id=member_id).all()
            if LabRole.lab_coordinator in (ms.roles or [])
        ]
        return Member.query.filter(
            Member.is_approved == False,  # noqa: E712
            Member.desired_lab_id.in_(ceo_lab_ids),
        ).all()
    return []


def _deadline_entries(
    activities: list[Activity], projects: list[Project], today
) -> list[dict]:
    """Combine activity deadlines and project end dates into deadline items, sorted by due_on."""
    entries: list[dict] = []
    for a in activities:
        due = a.deadline
        entries.append(
            {
                "type": "activity",
                "id": a.id,
                "title": a.title,
                "lab_id": a.lab_id,
                "lab_name": a.laboratory.name if a.laboratory else None,
                "status": a.status.value,
                "due_on": due.isoformat(),
                "days_left": (due - today).days,
                "overdue": (due - today).days < 0,
            }
        )
    for p in projects:
        due = p.end_date
        entries.append(
            {
                "type": "project",
                "id": p.id,
                "title": p.name,
                "lab_id": p.lab_id,
                "lab_name": p.laboratory.name if p.laboratory else None,
                "status": p.status.value,
                "due_on": due.isoformat(),
                "days_left": (due - today).days,
                "overdue": (due - today).days < 0,
            }
        )
    entries.sort(key=lambda e: e["due_on"])
    return entries


@bp.get("/summary")
@jwt_required()
def dashboard_summary():
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    today = datetime.now(timezone.utc).date()

    manager = _is_manager(claims, member_id)
    managed_lab_ids = _managed_lab_ids(claims, member_id)

    zero_counts = {
        "active_members": 0,
        "pending_members": 0,
        "activities_in_progress": 0,
        "activities_under_review": 0,
        "activities_completed": 0,
        "projects_active": 0,
        "inventory_items": 0,
    }

    pending_members = []
    upcoming_deadlines = []
    recent_activities = []
    my_activities = []
    my_projects = []
    my_deadlines = []

    if manager:
        counts = dict(zero_counts)
        if managed_lab_ids:
            counts["active_members"] = (
                db.session.query(Member.id)
                .join(LabMembership, LabMembership.member_id == Member.id)
                .filter(
                    LabMembership.lab_id.in_(managed_lab_ids),
                    Member.is_approved.is_(True),
                    Member.is_active.is_(True),
                )
                .distinct()
                .count()
            )
            counts["activities_in_progress"] = Activity.query.filter(
                Activity.lab_id.in_(managed_lab_ids),
                Activity.status == ActivityStatus.in_progress,
            ).count()
            counts["activities_under_review"] = Activity.query.filter(
                Activity.lab_id.in_(managed_lab_ids),
                Activity.status == ActivityStatus.under_review,
            ).count()
            counts["activities_completed"] = Activity.query.filter(
                Activity.lab_id.in_(managed_lab_ids),
                Activity.status == ActivityStatus.completed,
            ).count()
            counts["projects_active"] = Project.query.filter(
                Project.lab_id.in_(managed_lab_ids),
                Project.status == ProjectStatus.active,
            ).count()
            counts["inventory_items"] = InventoryItem.query.filter(
                InventoryItem.lab_id.in_(managed_lab_ids)
            ).count()

        # Pending members share the /members/pending visibility rule
        pending_members = _pending_members(claims, member_id)
        counts["pending_members"] = len(pending_members)

        pending_members = [
            {
                "member_id": m.id,
                "first_name": m.first_name,
                "last_name": m.last_name,
                "email": m.email,
                "desired_lab_id": m.desired_lab_id,
                "lab_name": m.desired_lab.name if m.desired_lab else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in pending_members
        ]

        if managed_lab_ids:
            deadline_acts = Activity.query.filter(
                Activity.lab_id.in_(managed_lab_ids),
                Activity.deadline.isnot(None),
            ).all()
            deadline_projs = Project.query.filter(
                Project.lab_id.in_(managed_lab_ids),
                Project.end_date.isnot(None),
            ).all()
            upcoming_deadlines = _deadline_entries(
                deadline_acts, deadline_projs, today
            )[:10]

            recent = (
                Activity.query.filter(Activity.lab_id.in_(managed_lab_ids))
                .order_by(Activity.created_at.desc())
                .limit(5)
                .all()
            )
            recent_activities = [
                {
                    "id": a.id,
                    "title": a.title,
                    "status": a.status.value,
                    "lab_id": a.lab_id,
                    "lab_name": a.laboratory.name if a.laboratory else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in recent
            ]
    else:
        counts = zero_counts

        my_acts = (
            Activity.query.filter(
                (Activity.participants.any(Member.id == member_id))
                | (Activity.in_charge.any(Member.id == member_id))
            )
            .order_by(Activity.created_at.desc())
            .limit(5)
            .all()
        )
        my_activities = [
            {
                "id": a.id,
                "title": a.title,
                "status": a.status.value,
                "lab_id": a.lab_id,
                "lab_name": a.laboratory.name if a.laboratory else None,
                "deadline": a.deadline.isoformat() if a.deadline else None,
                "days_left": (a.deadline - today).days if a.deadline else None,
            }
            for a in my_acts
        ]

        my_projs = (
            Project.query.filter(Project.members.any(Member.id == member_id))
            .limit(5)
            .all()
        )
        my_projects = [
            {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "lab_id": p.lab_id,
                "lab_name": p.laboratory.name if p.laboratory else None,
                "end_date": p.end_date.isoformat() if p.end_date else None,
            }
            for p in my_projs
        ]

        my_deadline_acts = Activity.query.filter(
            (Activity.participants.any(Member.id == member_id))
            | (Activity.in_charge.any(Member.id == member_id)),
            Activity.deadline.isnot(None),
        ).all()
        my_deadline_projs = Project.query.filter(
            Project.members.any(Member.id == member_id),
            Project.end_date.isnot(None),
        ).all()
        my_deadlines = _deadline_entries(
            my_deadline_acts, my_deadline_projs, today
        )[:10]

    return (
        jsonify(
            {
                "is_manager": manager,
                "counts": counts,
                "pending_members": pending_members,
                "upcoming_deadlines": upcoming_deadlines,
                "recent_activities": recent_activities,
                "my_activities": my_activities,
                "my_projects": my_projects,
                "my_deadlines": my_deadlines,
            }
        ),
        200,
    )


def _valid_status(enum_cls, raw: str | None) -> str | None:
    """Validate an optional ?status= query param against a status enum."""
    if not raw:
        return None
    values = {s.value for s in enum_cls}
    if raw not in values:
        abort(422, f"Invalid status. Allowed: {sorted(values)}")
    return raw


@bp.get("/activities")
@jwt_required()
def list_dashboard_activities():
    """All activities in scope (manager: managed labs; member: own), optional ?status= filter."""
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    status = _valid_status(ActivityStatus, request.args.get("status"))

    if _is_manager(claims, member_id):
        lab_ids = _managed_lab_ids(claims, member_id)
        if not lab_ids:
            return jsonify([]), 200
        query = Activity.query.filter(Activity.lab_id.in_(lab_ids))
    else:
        query = Activity.query.filter(
            (Activity.participants.any(Member.id == member_id))
            | (Activity.in_charge.any(Member.id == member_id))
        )

    if status:
        query = query.filter(Activity.status == status)

    acts = (
        query.order_by(
            Activity.deadline.asc().nullslast(), Activity.created_at.desc()
        )
        .all()
    )
    return (
        jsonify(
            [
                {
                    "id": a.id,
                    "title": a.title,
                    "status": a.status.value,
                    "activity_type": a.activity_type,
                    "deadline": a.deadline.isoformat() if a.deadline else None,
                    "lab_id": a.lab_id,
                    "lab_name": a.laboratory.name if a.laboratory else None,
                    "created_at": a.created_at.isoformat() if a.created_at else None,
                }
                for a in acts
            ]
        ),
        200,
    )


@bp.get("/projects")
@jwt_required()
def list_dashboard_projects():
    """All projects in scope (manager: managed labs; member: own), optional ?status= filter."""
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    status = _valid_status(ProjectStatus, request.args.get("status"))

    if _is_manager(claims, member_id):
        lab_ids = _managed_lab_ids(claims, member_id)
        if not lab_ids:
            return jsonify([]), 200
        query = Project.query.filter(Project.lab_id.in_(lab_ids))
    else:
        query = Project.query.filter(Project.members.any(Member.id == member_id))

    if status:
        query = query.filter(Project.status == status)

    projs = query.order_by(Project.name).all()
    return (
        jsonify(
            [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status.value,
                    "start_date": p.start_date.isoformat() if p.start_date else None,
                    "end_date": p.end_date.isoformat() if p.end_date else None,
                    "lab_id": p.lab_id,
                    "lab_name": p.laboratory.name if p.laboratory else None,
                }
                for p in projs
            ]
        ),
        200,
    )


@bp.get("/inventory")
@jwt_required()
def list_dashboard_inventory():
    """Inventory in scope (manager: managed labs; member: items assigned to them)."""
    claims = get_jwt()
    member_id = int(get_jwt_identity())

    if _is_manager(claims, member_id):
        lab_ids = _managed_lab_ids(claims, member_id)
        if not lab_ids:
            return jsonify([]), 200
        query = InventoryItem.query.filter(InventoryItem.lab_id.in_(lab_ids))
    else:
        query = InventoryItem.query.filter(InventoryItem.assigned_to_id == member_id)

    items = query.order_by(InventoryItem.name).all()
    return (
        jsonify(
            [
                {
                    "id": it.id,
                    "name": it.name,
                    "category": it.category,
                    "quantity": it.quantity,
                    "condition": it.condition.value,
                    "lab_id": it.lab_id,
                    "lab_name": it.laboratory.name if it.laboratory else None,
                    "assigned_to_id": it.assigned_to_id,
                    "assigned_to_name": (
                        f"{it.assigned_to.first_name} {it.assigned_to.last_name}"
                        if it.assigned_to else None
                    ),
                }
                for it in items
            ]
        ),
        200,
    )

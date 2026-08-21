"""Announcements — role-aware: managers publish, members read what targets them."""
from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from labhive.extensions import db
from labhive.models.announcement import Announcement
from labhive.models.lab_membership import LabMembership, MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.utils.notifications import notify

bp = Blueprint("announcements", __name__, url_prefix="/announcements")


def _managed_lab_ids(claims: dict, member_id: int) -> list[int]:
    if claims.get("is_super_admin"):
        return [lab.id for lab in Laboratory.query.all()]
    return [
        ms.lab_id
        for ms in LabMembership.query.filter_by(member_id=member_id).all()
        if set(MANAGER_ROLES) & set(ms.roles or [])
    ]


def _member_roles(member_id: int) -> set[str]:
    memberships = LabMembership.query.filter_by(member_id=member_id).all()
    roles: set[str] = set()
    for ms in memberships:
        roles.update(ms.roles or [])
    return roles


def _visible_announcements(member_id: int, claims: dict):
    """Announcements visible to a member.

    Super-admins see everything; lab managers see their labs' announcements;
    regular members see announcements of labs they belong to whose audience is
    empty (everyone) or intersects their roles.
    """
    if claims.get("is_super_admin"):
        return Announcement.query.filter_by(is_active=True).order_by(
            Announcement.is_pinned.desc(), Announcement.created_at.desc()
        )
    my_lab_ids = [ms.lab_id for ms in LabMembership.query.filter_by(member_id=member_id).all()]
    if not my_lab_ids:
        return Announcement.query.filter(False)
    my_roles = _member_roles(member_id)
    is_manager = bool(
        [
            ms
            for ms in LabMembership.query.filter_by(member_id=member_id).all()
            if set(MANAGER_ROLES) & set(ms.roles or [])
        ]
    )
    query = Announcement.query.filter(
        Announcement.is_active.is_(True),
        Announcement.lab_id.in_(my_lab_ids),
    )
    if not is_manager:
        # Members only see announcements that target them (empty audience = everyone)
        audience_conditions = [
            db.or_(
                Announcement.audience == [],
                Announcement.audience.is_(None),
                *[Announcement.audience.contains([role]) for role in my_roles],
            )
        ]
        query = query.filter(*audience_conditions)
    return query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())


def _announcement_payload(announcement: Announcement) -> dict:
    return {
        "id": announcement.id,
        "title": announcement.title,
        "body": announcement.body,
        "lab_id": announcement.lab_id,
        "lab_name": announcement.laboratory.name if announcement.laboratory else None,
        "audience": announcement.audience or [],
        "is_pinned": announcement.is_pinned,
        "is_active": announcement.is_active,
        "created_at": announcement.created_at.isoformat() if announcement.created_at else None,
        "updated_at": announcement.updated_at.isoformat() if announcement.updated_at else None,
        "author_id": announcement.author_id,
        "author_name": (
            f"{announcement.author.first_name} {announcement.author.last_name}"
            if announcement.author
            else None
        ),
    }


@bp.get("")
@jwt_required()
def list_announcements():
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    query = _visible_announcements(member_id, claims)

    pinned_only = request.args.get("pinned_only", "").lower() in ("1", "true", "yes")
    if pinned_only:
        query = query.filter(Announcement.is_pinned.is_(True))
    if request.args.get("lab_id", type=int):
        query = query.filter(Announcement.lab_id == request.args["lab_id"])

    return jsonify([_announcement_payload(a) for a in query.limit(100).all()]), 200


@bp.get("/<int:announcement_id>")
@jwt_required()
def get_announcement(announcement_id: int):
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    announcement = Announcement.query.filter_by(id=announcement_id).first()
    if not announcement or not announcement.is_active:
        abort(404, "Announcement not found.")
    visible = _visible_announcements(member_id, claims)
    if visible.filter(Announcement.id == announcement_id).first() is None:
        abort(403, "You cannot see this announcement.")
    return jsonify(_announcement_payload(announcement)), 200


@bp.post("")
@jwt_required()
def create_announcement():
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    lab_id = data.get("lab_id")
    if not lab_id:
        abort(422, "lab_id is required.")
    lab = db.session.get(Laboratory, int(lab_id))
    if not lab:
        abort(404, "Laboratory not found.")

    managed = _managed_lab_ids(claims, member_id)
    if lab.id not in managed:
        abort(403, "You must be a manager of this laboratory to post announcements.")

    title = (data.get("title") or "").strip()
    if not title:
        abort(422, "title is required.")

    announcement = Announcement(
        title=title,
        body=data.get("body"),
        author_id=member_id,
        lab_id=lab.id,
        audience=data.get("audience") or [],
        is_pinned=bool(data.get("is_pinned", False)),
    )
    db.session.add(announcement)
    db.session.flush()

    # Notify the audience: everyone in the lab, or members with one of the target roles
    audience = announcement.audience or []
    if not audience:
        target_ids = [
            row[0]
            for row in db.session.query(LabMembership.member_id)
            .filter(LabMembership.lab_id == lab.id)
            .distinct()
            .all()
        ]
    else:
        target_ids = []
        memberships = LabMembership.query.filter_by(lab_id=lab.id).all()
        for ms in memberships:
            if set(audience) & set(ms.roles or []):
                target_ids.append(ms.member_id)
    target_ids = [mid for mid in target_ids if mid != member_id]

    notify(target_ids, "announcement", announcement.title, f"/announcements/{announcement.id}")
    db.session.commit()
    return jsonify(_announcement_payload(announcement)), 201


@bp.put("/<int:announcement_id>")
@jwt_required()
def update_announcement(announcement_id: int):
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    announcement = Announcement.query.filter_by(id=announcement_id).first()
    if not announcement:
        abort(404, "Announcement not found.")

    managed = _managed_lab_ids(claims, member_id)
    if announcement.lab_id not in managed and announcement.author_id != member_id:
        abort(403, "Only the author or a lab manager can edit this announcement.")

    data = request.get_json(silent=True) or {}
    if "title" in data:
        title = (data["title"] or "").strip()
        if not title:
            abort(422, "title is required.")
        announcement.title = title
    if "body" in data:
        announcement.body = data.get("body")
    if "audience" in data:
        announcement.audience = data.get("audience") or []
    if "is_pinned" in data:
        announcement.is_pinned = bool(data["is_pinned"])
    if "is_active" in data:
        announcement.is_active = bool(data["is_active"])
    db.session.commit()
    return jsonify(_announcement_payload(announcement)), 200


@bp.delete("/<int:announcement_id>")
@jwt_required()
def delete_announcement(announcement_id: int):
    claims = get_jwt()
    member_id = int(get_jwt_identity())
    announcement = Announcement.query.filter_by(id=announcement_id).first()
    if not announcement:
        abort(404, "Announcement not found.")
    managed = _managed_lab_ids(claims, member_id)
    if announcement.lab_id not in managed and announcement.author_id != member_id:
        abort(403, "Only the author or a lab manager can delete this announcement.")
    db.session.delete(announcement)
    db.session.commit()
    return "", 204

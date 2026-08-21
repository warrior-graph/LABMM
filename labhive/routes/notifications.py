"""Notifications — my inbox with a lazy deadline sync (7/3/1 days ahead)."""
from datetime import datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from labhive.extensions import db
from labhive.models.activity import Activity
from labhive.models.member import Member
from labhive.models.notification import Notification
from labhive.utils.notifications import notify

bp = Blueprint("notifications", __name__, url_prefix="/notifications")

DEADLINE_WINDOWS = (7, 3, 1)


def _sync_deadline_notifications(member_id: int) -> None:
    """Create activity_deadline notifications for the member's activities due in 7/3/1 days.

    Lazy approach (no scheduler): runs whenever the user opens the notification list.
    Deduplicated by (member, link) with an unread notification still pending.
    """
    today = datetime.now(timezone.utc).date()
    windows = {today + timedelta(days=n): n for n in DEADLINE_WINDOWS}

    for deadline, days in windows.items():
        acts = Activity.query.filter(
            Activity.deadline == deadline,
            (
                Activity.participants.any(Member.id == member_id)
                | (Activity.in_charge.any(Member.id == member_id))
            ),
        ).all()
        for act in acts:
            link = f"/labs/{act.lab_id}/activities/{act.id}"
            exists = Notification.query.filter_by(
                member_id=member_id,
                type="activity_deadline",
                link=link,
                is_read=False,
            ).first()
            if exists:
                continue
            suffix = "amanhã" if days == 1 else f"em {days} dias"
            notify(
                [member_id],
                "activity_deadline",
                f"Prazo {suffix}: {act.title}",
                link,
            )
    db.session.commit()


def _dump(n: Notification) -> dict:
    return {
        "id": n.id,
        "type": n.type,
        "message": n.message,
        "link": n.link,
        "is_read": n.is_read,
        "created_at": n.created_at.isoformat() if n.created_at else None,
    }


@bp.get("")
@jwt_required()
def list_notifications():
    member_id = int(get_jwt_identity())
    _sync_deadline_notifications(member_id)

    query = Notification.query.filter_by(member_id=member_id)
    if request.args.get("unread_only", "").lower() in ("1", "true", "yes"):
        query = query.filter_by(is_read=False)
    query = query.order_by(Notification.created_at.desc(), Notification.id.desc())
    return jsonify([_dump(n) for n in query.limit(100).all()]), 200


@bp.get("/unread-count")
@jwt_required()
def unread_count():
    member_id = int(get_jwt_identity())
    _sync_deadline_notifications(member_id)
    count = Notification.query.filter_by(member_id=member_id, is_read=False).count()
    return jsonify({"count": count}), 200


@bp.post("/<int:notification_id>/read")
@jwt_required()
def mark_read(notification_id: int):
    member_id = int(get_jwt_identity())
    notification = Notification.query.filter_by(
        id=notification_id, member_id=member_id
    ).first()
    if not notification:
        return jsonify(error="Notification not found."), 404
    notification.is_read = True
    db.session.commit()
    return jsonify(_dump(notification)), 200


@bp.post("/read-all")
@jwt_required()
def mark_all_read():
    member_id = int(get_jwt_identity())
    Notification.query.filter_by(member_id=member_id, is_read=False).update(
        {"is_read": True}
    )
    db.session.commit()
    return jsonify({"ok": True}), 200

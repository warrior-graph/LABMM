from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required

from labhive.extensions import db
from labhive.models.invite import InviteToken
from labhive.models.lab_membership import MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.utils.decorators import require_lab_role

bp = Blueprint("invites", __name__)


@bp.post("/labs/<int:lab_id>/invites")
@require_lab_role(*MANAGER_ROLES)
def create_invite(lab_id: int):
    """Generate a time-limited invite link for joining a laboratory."""
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    creator = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}
    try:
        days = int(data.get("days", 7))
    except (TypeError, ValueError):
        days = 7
    invite = InviteToken.generate(lab_id, creator, days=days)
    db.session.add(invite)
    db.session.commit()
    return (
        jsonify(
            {
                "token": invite.token,
                "expires_at": invite.expires_at.isoformat(),
                "url": f"/register?invite={invite.token}",
            }
        ),
        201,
    )


@bp.get("/invites/<token>")
def validate_invite(token: str):
    """Public validation of an invite link (used by the register form)."""
    invite = InviteToken.query.filter_by(token=token).first()
    if not invite or invite.used_at is not None or invite.is_expired:
        abort(404, "Invalid or expired invite link.")
    return (
        jsonify(
            {
                "lab_id": invite.lab_id,
                "lab_name": invite.laboratory.name if invite.laboratory else None,
                "expires_at": invite.expires_at.isoformat(),
            }
        ),
        200,
    )

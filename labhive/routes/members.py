from datetime import datetime, timezone

from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.lab_membership import CompensationType, LabMembership, LabRole, MANAGER_ROLES, ROLE_LEVEL
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.role import Role


def _get_role_level(role_key: str) -> int:
    """Level for a role key — checks system ROLE_LEVEL first, then DB for custom roles."""
    level = ROLE_LEVEL.get(role_key)
    if level is not None:
        return level
    role = Role.query.filter_by(key=role_key).first()
    return role.level if role else 99


def _primary_role_level(ms: LabMembership) -> int:
    """Level for a membership — the level of its highest-authority role."""
    return min((_get_role_level(r) for r in (ms.roles or [])), default=99)
from labhive.schemas.lab_membership_schema import (
    lab_membership_input_schema,
    lab_membership_schema,
    lab_membership_update_schema,
    lab_memberships_schema,
)
from labhive.schemas.member_schema import member_schema, members_schema
from labhive.utils.decorators import require_lab_member, require_lab_role

bp = Blueprint("members", __name__)


@bp.get("/members/<int:member_id>")
@jwt_required()
def get_member_detail(member_id: int):
    """Super-admin or Lab Coordinator: return a single member with full lab_memberships."""
    claims = get_jwt()
    current_id = get_jwt_identity()

    if not claims.get("is_super_admin"):
        # Lab Coordinators may access members that belong to one of their labs
        ceo_lab_ids = [
            m.lab_id for m in LabMembership.query.filter_by(member_id=current_id).all()
            if LabRole.lab_coordinator in (m.roles or [])
        ]
        if not ceo_lab_ids:
            abort(403, "Super-admin or Lab Coordinator access required.")
        in_lab = LabMembership.query.filter(
            LabMembership.member_id == member_id,
            LabMembership.lab_id.in_(ceo_lab_ids)
        ).first()
        if not in_lab:
            abort(403, "Access denied.")

    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    return jsonify(member_schema.dump(member)), 200


@bp.get("/members")
@jwt_required()
def list_all_members():
    """Super-admin or Lab Coordinator: list members (Lab Coordinators see only their labs' members)."""
    claims = get_jwt()
    current_id = get_jwt_identity()

    if claims.get("is_super_admin"):
        members = Member.query.order_by(Member.last_name, Member.first_name).all()
        return jsonify(members_schema.dump(members)), 200

    # Allow Lab Coordinators to list members of labs they lead
    ceo_lab_ids = [
        m.lab_id for m in LabMembership.query.filter_by(member_id=current_id).all()
        if LabRole.lab_coordinator in (m.roles or [])
    ]
    if not ceo_lab_ids:
        abort(403, "Access denied.")

    member_ids = [
        row[0] for row in db.session.query(LabMembership.member_id)
        .filter(LabMembership.lab_id.in_(ceo_lab_ids))
        .distinct()
        .all()
    ]
    members = Member.query.filter(Member.id.in_(member_ids)).order_by(
        Member.last_name, Member.first_name
    ).all()
    return jsonify(members_schema.dump(members)), 200


@bp.get("/labs/<int:lab_id>/members")
@require_lab_member
def list_members(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    memberships = LabMembership.query.filter_by(lab_id=lab_id).all()
    return jsonify(lab_memberships_schema.dump(memberships)), 200


@bp.get("/labs/<int:lab_id>/org")
@require_lab_member
def lab_org_chart(lab_id: int):
    """Deterministic org-chart tree.

    Returns a flat list of memberships, each annotated with resolved_reports_to_id,
    plus the single root_id. Rules:
      1. explicit reports_to wins only if the target is in the lab, not self, and
         has a strictly more-senior (lower) role level — this guarantees no cycles;
      2. otherwise attach to the most-senior member above (lowest role level);
      3. fall back to the root.
    Root = the lab_coordinator if present, else the most-senior member.
    """
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    memberships = LabMembership.query.filter_by(lab_id=lab_id).all()
    if not memberships:
        return jsonify({"root_id": None, "memberships": []}), 200

    by_id = {m.member_id: m for m in memberships}

    coordinators = [m for m in memberships if LabRole.lab_coordinator in (m.roles or [])]
    root = coordinators[0] if coordinators else min(
        memberships, key=_primary_role_level
    )

    resolved: dict[int, int | None] = {}
    for m in memberships:
        if m.member_id == root.member_id:
            resolved[m.member_id] = None
            continue

        my_level = _primary_role_level(m)
        # Explicit reporting, only if it points up the hierarchy
        rid = m.reports_to_id
        if rid and rid in by_id and rid != m.member_id:
            if _primary_role_level(by_id[rid]) < my_level:
                resolved[m.member_id] = rid
                continue

        # Nearest level strictly above me (level-1 if present)
        seniors = [
            o for o in memberships
            if o.member_id != m.member_id and _primary_role_level(o) < my_level
        ]
        if seniors:
            parent = max(seniors, key=lambda o: _primary_role_level(o))
            resolved[m.member_id] = parent.member_id
        else:
            resolved[m.member_id] = root.member_id

    payload = [
        {**lab_membership_schema.dump(m), "resolved_reports_to_id": resolved[m.member_id]}
        for m in memberships
    ]
    return jsonify({"root_id": root.member_id, "memberships": payload}), 200


@bp.post("/labs/<int:lab_id>/members")
@require_lab_role(*MANAGER_ROLES)
def add_member(lab_id: int):
    claims = get_jwt()
    requester_id = int(get_jwt_identity())

    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")

    data = request.get_json(silent=True) or {}
    try:
        payload = lab_membership_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422

    role_keys = payload["roles"]
    role_defs = []
    for rk in role_keys:
        rd = Role.query.filter_by(key=rk).first()
        if not rd:
            return jsonify(error=f"Unknown role: {rk}"), 422
        role_defs.append(rd)
    min_new_level = min(rd.level for rd in role_defs)

    member = db.session.get(Member, payload["member_id"])
    if not member:
        abort(404, "Member not found.")

    existing = LabMembership.query.filter_by(
        member_id=member.id, lab_id=lab_id
    ).first()
    if existing:
        return jsonify(error="Member already belongs to this laboratory."), 409
    
    # Hierarchy check: super-admins bypass; others can only assign roles below their own level
    if not claims.get("is_super_admin"):
        requester_ms = LabMembership.query.filter_by(
            member_id=requester_id, lab_id=lab_id
        ).first()
        if _primary_role_level(requester_ms) >= min_new_level:
            abort(403, "You can only assign roles below your own level.")

    rid = payload.get("reports_to_id")
    if rid is not None:
        if not LabMembership.query.filter_by(member_id=rid, lab_id=lab_id).first():
            abort(422, "reports_to_id must refer to a member of this laboratory.")
        if rid == payload["member_id"]:
            abort(422, "Member cannot report to themselves.")

    ct = payload.get("compensation_type")
    membership = LabMembership(
        member_id=member.id,
        lab_id=lab_id,
        roles=role_keys,
        specialization=payload.get("specialization"),
        compensation_type=CompensationType(ct) if ct else None,
        compensation_value=payload.get("compensation_value"),
        reports_to_id=rid,
    )
    db.session.add(membership)
    db.session.commit()
    return jsonify(lab_membership_schema.dump(membership)), 201


@bp.get("/labs/<int:lab_id>/members/<int:member_id>")
@require_lab_member
def get_member(lab_id: int, member_id: int):
    membership = LabMembership.query.filter_by(
        lab_id=lab_id, member_id=member_id
    ).first()
    if not membership:
        abort(404, "Member not found in this laboratory.")
    return jsonify(lab_membership_schema.dump(membership)), 200


@bp.put("/labs/<int:lab_id>/members/<int:member_id>")
@require_lab_member
def update_member_role(lab_id: int, member_id: int):
    claims = get_jwt()
    requester_id = int(get_jwt_identity())
    is_self = requester_id == member_id

    membership = LabMembership.query.filter_by(
        lab_id=lab_id, member_id=member_id
    ).first()
    if not membership:
        abort(404, "Member not found in this laboratory.")

    data = request.get_json(silent=True) or {}
    try:
        payload = lab_membership_update_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422

    role_keys = payload["roles"]
    role_defs = []
    for rk in role_keys:
        rd = Role.query.filter_by(key=rk).first()
        if not rd:
            return jsonify(error=f"Unknown role: {rk}"), 422
        role_defs.append(rd)
    min_new_level = min(rd.level for rd in role_defs)

    if not claims.get("is_super_admin"):
        requester_ms = LabMembership.query.filter_by(
            member_id=requester_id, lab_id=lab_id
        ).first()
        requester_level = _primary_role_level(requester_ms)
        target_level = _primary_role_level(membership)

        if is_self:
            # Self-demotion: only a Lab Coordinator may step down, and cannot reassign Lab Coordinator to themselves
            if target_level != 0:
                abort(403, "You cannot change your own role.")
            if min_new_level == 0:
                abort(403, "You cannot keep the Lab Coordinator role via self-demotion.")
        else:
            if requester_level >= target_level:
                abort(403, "You can only manage members below your role level.")
            if requester_level >= min_new_level:
                abort(403, "You can only assign roles below your own level.")

    membership.roles = role_keys
    if "specialization" in data:
        membership.specialization = payload.get("specialization")
    ct = payload.get("compensation_type")
    if "compensation_type" in data:
        membership.compensation_type = CompensationType(ct) if ct else None
    if "compensation_value" in data:
        membership.compensation_value = payload.get("compensation_value")

    if "reports_to_id" in data:
        if not claims.get("is_super_admin"):
            if _primary_role_level(requester_ms) != 0:
                abort(403, "Only the Lab Coordinator or a super admin can set the reporting structure.")
        rid = payload.get("reports_to_id")
        if rid is not None:
            if not LabMembership.query.filter_by(member_id=rid, lab_id=lab_id).first():
                abort(422, "reports_to_id must refer to a member of this laboratory.")
        membership.reports_to_id = rid

    db.session.commit()
    return jsonify(lab_membership_schema.dump(membership)), 200


@bp.delete("/labs/<int:lab_id>/members/<int:member_id>")
@require_lab_member
def remove_member(lab_id: int, member_id: int):
    claims = get_jwt()
    requester_id = int(get_jwt_identity())

    if requester_id == member_id:
        abort(403, "You cannot remove yourself from a lab.")

    membership = LabMembership.query.filter_by(
        lab_id=lab_id, member_id=member_id
    ).first()
    if not membership:
        abort(404, "Member not found in this laboratory.")

    if not claims.get("is_super_admin"):
        requester_ms = LabMembership.query.filter_by(
            member_id=requester_id, lab_id=lab_id
        ).first()
        if _primary_role_level(requester_ms) >= _primary_role_level(membership):
            abort(403, "You can only remove members below your role level.")

    db.session.delete(membership)
    db.session.commit()
    return "", 204


# --- Own profile update (any authenticated lab member or super-admin) ---

@bp.put("/members/<int:member_id>")
@jwt_required()
def update_own_profile(member_id: int):
    claims = get_jwt()
    identity = int(get_jwt_identity())

    # Members can only edit themselves; super-admins can edit anyone
    if identity != member_id and not claims.get("is_super_admin"):
        abort(403, "You can only update your own profile.")

    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")

    data = request.get_json(silent=True) or {}
    allowed = ("first_name", "last_name", "lattes_url", "orcid", "github_url")
    for field in allowed:
        if field in data:
            setattr(member, field, data[field])

    # Super-admins can promote/demote professor status
    if claims.get("is_super_admin") and "is_professor" in data:
        member.is_professor = bool(data["is_professor"])

    if "password" in data:
        member.set_password(data["password"])

    db.session.commit()
    return jsonify(member_schema.dump(member)), 200


@bp.post("/labs/<int:lab_id>/members/<int:member_id>/leave")
@require_lab_role(*MANAGER_ROLES)
def mark_member_left(lab_id: int, member_id: int):
    """Soft offboarding: record the leave date without deleting the membership history."""
    membership = LabMembership.query.filter_by(lab_id=lab_id, member_id=member_id).first()
    if not membership:
        abort(404, "Member not found in this laboratory.")
    membership.left_at = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(lab_membership_schema.dump(membership)), 200


@bp.post("/labs/<int:lab_id>/members/<int:member_id>/rejoin")
@require_lab_role(*MANAGER_ROLES)
def rejoin_member(lab_id: int, member_id: int):
    """Clear the leave date, re-activating the membership."""
    membership = LabMembership.query.filter_by(lab_id=lab_id, member_id=member_id).first()
    if not membership:
        abort(404, "Member not found in this laboratory.")
    membership.left_at = None
    db.session.commit()
    return jsonify(lab_membership_schema.dump(membership)), 200


@bp.get("/members/<int:member_id>/history")
@jwt_required()
def member_history(member_id: int):
    """Membership history (self or super-admin): labs, roles, joined/left dates."""
    claims = get_jwt()
    identity = int(get_jwt_identity())
    if identity != member_id and not claims.get("is_super_admin"):
        abort(403, "You can only view your own history.")
    memberships = LabMembership.query.filter_by(member_id=member_id).all()
    return (
        jsonify(
            [
                {
                    "lab_id": ms.lab_id,
                    "lab_name": ms.laboratory.name if ms.laboratory else None,
                    "roles": ms.roles or [],
                    "joined_at": ms.joined_at.isoformat() if ms.joined_at else None,
                    "left_at": ms.left_at.isoformat() if ms.left_at else None,
                }
                for ms in memberships
            ]
        ),
        200,
    )


@bp.get("/members/lookup")
@jwt_required()
def lookup_member():
    """Look up a member by CPF. Returns basic member info (id, name, email)."""
    raw = request.args.get("cpf", "")
    cpf = raw.replace(".", "").replace("-", "").strip()
    if not cpf or not cpf.isdigit() or len(cpf) != 11:
        return jsonify(error="Invalid CPF."), 422
    member = Member.query.filter_by(cpf=cpf).first()
    if not member:
        abort(404, "No member found with this CPF.")
    return jsonify(member_schema.dump(member)), 200


@bp.get("/members/pending")
@jwt_required()
def list_pending_members():
    """Return all unapproved members. Professors see only their Lab Coordinator labs' pending members."""
    claims = get_jwt()
    if claims.get("is_super_admin"):
        pending = Member.query.filter_by(is_approved=False).all()
    elif claims.get("is_professor"):
        member_id = int(get_jwt_identity())
        ceo_lab_ids = [
            m.lab_id for m in LabMembership.query.filter_by(member_id=member_id).all()
            if LabRole.lab_coordinator in (m.roles or [])
        ]
        pending = Member.query.filter(
            Member.is_approved == False,  # noqa: E712
            Member.desired_lab_id.in_(ceo_lab_ids),
        ).all()
    else:
        abort(403, "Professor or super-admin access required.")
    return jsonify(members_schema.dump(pending)), 200


@bp.post("/members/<int:member_id>/approve")
@jwt_required()
def approve_member(member_id: int):
    """Approve a pending member. Professors may only approve members for their Lab Coordinator labs."""
    claims = get_jwt()
    is_super_admin = claims.get("is_super_admin")
    is_professor = claims.get("is_professor")
    if not (is_super_admin or is_professor):
        abort(403, "Professor or super-admin access required.")

    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member.is_approved:
        return jsonify(member_schema.dump(member)), 200

    if not is_super_admin:
        # Professors may only approve members assigned to their Lab Coordinator labs
        caller_id = int(get_jwt_identity())
        ceo_lab_ids = [
            m.lab_id for m in LabMembership.query.filter_by(member_id=caller_id).all()
            if LabRole.lab_coordinator in (m.roles or [])
        ]
        if member.desired_lab_id not in ceo_lab_ids:
            abort(403, "You can only approve members who requested access to your laboratory.")

    member.is_approved = True
    member.desired_lab_id = None
    from labhive.utils.notifications import notify

    notify([member.id], "member_approved", "Sua conta foi aprovada!", "/labs")
    db.session.commit()
    return jsonify(member_schema.dump(member)), 200


@bp.post("/members/<int:member_id>/deactivate")
@jwt_required()
def deactivate_member(member_id: int):
    """Super-admin: deactivate a member account (blocks login)."""
    if not get_jwt().get("is_super_admin"):
        abort(403, "Super-admin access required.")
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member.is_super_admin:
        abort(400, "Cannot deactivate a super-admin account.")
    member.is_active = False
    db.session.commit()
    return jsonify(member_schema.dump(member)), 200


@bp.post("/members/<int:member_id>/activate")
@jwt_required()
def activate_member(member_id: int):
    """Super-admin: reactivate a previously deactivated member."""
    if not get_jwt().get("is_super_admin"):
        abort(403, "Super-admin access required.")
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    member.is_active = True
    db.session.commit()
    return jsonify(member_schema.dump(member)), 200

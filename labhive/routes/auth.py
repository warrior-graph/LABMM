from flask import Blueprint, abort, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.member import Member
from labhive.schemas.member_schema import member_input_schema, member_schema

bp = Blueprint("auth", __name__, url_prefix="/auth")


def _make_tokens(member: Member) -> dict:
    additional_claims = {
        "is_super_admin": member.is_super_admin,
        "is_professor": member.is_professor,
    }
    access_token = create_access_token(
        identity=str(member.id), additional_claims=additional_claims
    )
    refresh_token = create_refresh_token(
        identity=str(member.id), additional_claims=additional_claims
    )
    return {"access_token": access_token, "refresh_token": refresh_token}


@bp.post("/register")
def register():
    """
    Open to anyone. Bootstrap creates the super-admin (auto-approved).
    Professors/admins registering via JWT create an auto-approved account.
    Self-registration creates a pending account that must be approved by a lab professor.
    """
    from flask_jwt_extended import verify_jwt_in_request
    is_bootstrap = Member.query.count() == 0

    verify_jwt_in_request(optional=True)
    claims = get_jwt()

    data = request.get_json(silent=True) or {}

    # Normalize email
    if "email" in data:
        data = {**data, "email": data["email"].strip().lower()}

    # CPF is required — validate and normalize before schema load
    raw_cpf = data.get("cpf") or ""
    cpf_digits = str(raw_cpf).strip().replace(".", "").replace("-", "")
    if not cpf_digits.isdigit() or len(cpf_digits) != 11:
        return jsonify(errors={"cpf": ["CPF is required and must be exactly 11 digits."]}), 422

    # Inject normalized CPF so the schema sees the clean value
    data = {**data, "cpf": cpf_digits}

    try:
        member = member_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422

    if Member.query.filter_by(email=member.email).first():
        return jsonify(error="Email already registered."), 409

    if Member.query.filter_by(cpf=cpf_digits).first():
        return jsonify(error="CPF already registered."), 409

    member.cpf = cpf_digits
    member.set_password(data.get("password", ""))

    is_auto_approved = is_bootstrap or bool(claims.get("is_super_admin") or claims.get("is_professor"))
    member.is_approved = is_auto_approved

    if is_bootstrap:
        member.is_super_admin = True
    elif not is_auto_approved:
        # Self-registration: store desired lab for professor routing
        desired_lab_id = data.get("desired_lab_id")
        if desired_lab_id:
            from labhive.models.laboratory import Laboratory
            lab = db.session.get(Laboratory, int(desired_lab_id))
            if not lab:
                return jsonify(error="Selected laboratory not found."), 404
            member.desired_lab_id = lab.id

    # Any registrant can declare professor status
    if data.get("is_professor"):
        member.is_professor = True

    db.session.add(member)
    db.session.commit()

    if not is_auto_approved and member.desired_lab_id:
        # Notify managers of the desired lab that a member is waiting for approval
        from labhive.models.lab_membership import LabMembership, MANAGER_ROLES
        from labhive.utils.notifications import notify

        manager_ids = [
            row[0]
            for row in db.session.query(LabMembership.member_id)
            .filter(
                LabMembership.lab_id == member.desired_lab_id,
            )
            .all()
        ]
        manager_ids = [
            mid
            for mid in manager_ids
            if set(MANAGER_ROLES)
            & set(
                LabMembership.query.filter_by(
                    member_id=mid, lab_id=member.desired_lab_id
                ).first().roles or []
            )
        ]
        notify(
            manager_ids,
            "member_pending",
            f"Novo membro aguardando aprovação: {member.first_name} {member.last_name}",
            "/admin/pending",
        )
        db.session.commit()

    if is_auto_approved:
        tokens = _make_tokens(member)
        return jsonify(member=member_schema.dump(member), **tokens), 201
    else:
        return jsonify(member=member_schema.dump(member)), 201


@bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    member = Member.query.filter_by(email=email).first()
    if not member or not member.check_password(password):
        abort(401, "Invalid email or password.")

    if not member.is_approved:
        abort(403, "Your account is pending approval by your lab professor.")

    if not member.is_active:
        abort(403, "Your account has been deactivated. Please contact an administrator.")

    return jsonify(member=member_schema.dump(member), **_make_tokens(member)), 200


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    member = db.session.get(Member, int(identity))
    if not member:
        abort(401, "Member not found.")
    additional_claims = {
        "is_super_admin": member.is_super_admin,
        "is_professor": member.is_professor,
    }
    access_token = create_access_token(
        identity=identity, additional_claims=additional_claims
    )
    return jsonify(access_token=access_token), 200


@bp.get("/me")
@jwt_required()
def me():
    identity = get_jwt_identity()
    member = db.session.get(Member, int(identity))
    if not member:
        abort(401, "Member not found.")
    return jsonify(member_schema.dump(member)), 200

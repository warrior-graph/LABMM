from functools import wraps

from flask import abort
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from labhive.models.lab_membership import LabMembership, LabRole, MANAGER_ROLES


def require_super_admin(fn):
    """Allow only super-admins."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if not claims.get("is_super_admin"):
            abort(403, "Super-admin access required.")
        return fn(*args, **kwargs)
    return wrapper


def require_professor_or_super_admin(fn):
    """Allow professors and super-admins (for lab creation)."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if not (claims.get("is_super_admin") or claims.get("is_professor")):
            abort(403, "Professor or super-admin access required.")
        return fn(*args, **kwargs)
    return wrapper


def require_lab_role(*allowed_roles: LabRole):
    """
    Allow access if the authenticated member has one of the given roles
    in the lab identified by the ``lab_id`` URL parameter.
    Super-admins always pass.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()

            if claims.get("is_super_admin"):
                return fn(*args, **kwargs)

            member_id = int(claims["sub"])
            lab_id = kwargs.get("lab_id")
            if lab_id is None:
                abort(400, "lab_id missing from URL.")

            membership = LabMembership.query.filter_by(
                member_id=member_id, lab_id=lab_id
            ).first()

            if membership is None:
                abort(403, "You are not a member of this laboratory.")

            if not any(r in allowed_roles for r in membership.roles):
                abort(403, "Insufficient role for this action.")

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_lab_member(fn):
    """Allow any authenticated member of the lab regardless of role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        claims = get_jwt()
        if claims.get("is_super_admin"):
            return fn(*args, **kwargs)
        member_id = int(claims["sub"])
        lab_id = kwargs.get("lab_id")
        if lab_id is None:
            abort(400, "lab_id missing from URL.")
        membership = LabMembership.query.filter_by(
            member_id=member_id, lab_id=lab_id
        ).first()
        if membership is None:
            abort(403, "You are not a member of this laboratory.")
        return fn(*args, **kwargs)
    return wrapper

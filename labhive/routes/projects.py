from flask import Blueprint, abort, jsonify, request
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.lab_membership import LabMembership, LabRole, MANAGER_ROLES
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.project import Project
from labhive.schemas.project_schema import (
    project_input_schema,
    project_schema,
    projects_schema,
)
from labhive.utils.decorators import require_lab_member, require_lab_role

bp = Blueprint("projects", __name__)


@bp.get("/labs/<int:lab_id>/projects")
@require_lab_member
def list_projects(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    return jsonify(projects_schema.dump(lab.projects)), 200


@bp.post("/labs/<int:lab_id>/projects")
@require_lab_role(*MANAGER_ROLES, LabRole.tech_lead)
def create_project(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    data = request.get_json(silent=True) or {}

    # Validate tech_lead_id is a member of this lab (if provided)
    tech_lead_id = data.get("tech_lead_id")
    if tech_lead_id:
        tech_lead_membership = LabMembership.query.filter_by(
            member_id=tech_lead_id, lab_id=lab_id
        ).first()
        if not tech_lead_membership:
            return jsonify(error="Tech Lead must be a member of this laboratory."), 422

    try:
        project = project_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    project.lab_id = lab_id
    db.session.add(project)
    db.session.commit()
    return jsonify(project_schema.dump(project)), 201


@bp.get("/labs/<int:lab_id>/projects/<int:project_id>")
@require_lab_member
def get_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    return jsonify(project_schema.dump(project)), 200


@bp.put("/labs/<int:lab_id>/projects/<int:project_id>")
@require_lab_role(*MANAGER_ROLES, LabRole.tech_lead)
def update_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    data = request.get_json(silent=True) or {}
    try:
        project = project_input_schema.load(data, instance=project, partial=True)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    db.session.commit()
    return jsonify(project_schema.dump(project)), 200


@bp.delete("/labs/<int:lab_id>/projects/<int:project_id>")
@require_lab_role(*MANAGER_ROLES)
def delete_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    db.session.delete(project)
    db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/projects/<int:project_id>/members")
@require_lab_role(*MANAGER_ROLES)
def add_member_to_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    data = request.get_json(silent=True) or {}
    member_id = data.get("member_id")
    if not member_id:
        return jsonify(error="'member_id' is required."), 422
    member = db.session.get(Member, member_id)
    if not member:
        abort(404, "Member not found.")
    if member in project.members:
        return jsonify(error="Member already in this project."), 409
    project.members.append(member)
    db.session.commit()
    return jsonify(project_schema.dump(project)), 200


@bp.delete("/labs/<int:lab_id>/projects/<int:project_id>/members/<int:member_id>")
@require_lab_role(*MANAGER_ROLES)
def remove_member_from_project(lab_id: int, project_id: int, member_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    member = db.session.get(Member, member_id)
    if not member or member not in project.members:
        abort(404, "Member not found in this project.")
    project.members.remove(member)
    db.session.commit()
    return "", 204


@bp.post("/labs/<int:lab_id>/projects/<int:project_id>/deactivate")
@require_lab_role(*MANAGER_ROLES, LabRole.lab_coordinator)
def deactivate_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    project.is_active = False
    db.session.commit()
    return jsonify(project_schema.dump(project)), 200


@bp.post("/labs/<int:lab_id>/projects/<int:project_id>/activate")
@require_lab_role(*MANAGER_ROLES, LabRole.lab_coordinator)
def activate_project(lab_id: int, project_id: int):
    project = Project.query.filter_by(id=project_id, lab_id=lab_id).first()
    if not project:
        abort(404, "Project not found.")
    project.is_active = True
    db.session.commit()
    return jsonify(project_schema.dump(project)), 200

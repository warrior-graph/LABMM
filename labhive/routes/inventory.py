from flask import Blueprint, abort, jsonify, request
from marshmallow import ValidationError

from labhive.extensions import db
from labhive.models.inventory import InventoryItem
from labhive.models.lab_membership import LabRole
from labhive.models.laboratory import Laboratory
from labhive.schemas.inventory_schema import (
    inventory_item_input_schema,
    inventory_item_schema,
    inventory_items_schema,
)
from labhive.utils.decorators import require_lab_role, require_lab_member

bp = Blueprint("inventory", __name__)

_MANAGER_ROLES = (
    LabRole.lab_coordinator,
    LabRole.engineering_manager,
    LabRole.project_manager,
    LabRole.chief_scientist,
)


@bp.get("/labs/<int:lab_id>/inventory")
@require_lab_member
def list_inventory(lab_id: int):
    """All lab members can view inventory."""
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    return jsonify(inventory_items_schema.dump(lab.inventory_items)), 200


@bp.get("/labs/<int:lab_id>/inventory/<int:item_id>")
@require_lab_member
def get_inventory_item(lab_id: int, item_id: int):
    item = InventoryItem.query.filter_by(id=item_id, lab_id=lab_id).first()
    if not item:
        abort(404, "Inventory item not found.")
    return jsonify(inventory_item_schema.dump(item)), 200


@bp.post("/labs/<int:lab_id>/inventory")
@require_lab_role(*_MANAGER_ROLES)
def create_inventory_item(lab_id: int):
    lab = db.session.get(Laboratory, lab_id)
    if not lab:
        abort(404, "Laboratory not found.")
    data = request.get_json(silent=True) or {}
    try:
        item = inventory_item_input_schema.load(data)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    item.lab_id = lab_id
    db.session.add(item)
    db.session.commit()
    return jsonify(inventory_item_schema.dump(item)), 201


@bp.put("/labs/<int:lab_id>/inventory/<int:item_id>")
@require_lab_role(*_MANAGER_ROLES)
def update_inventory_item(lab_id: int, item_id: int):
    item = InventoryItem.query.filter_by(id=item_id, lab_id=lab_id).first()
    if not item:
        abort(404, "Inventory item not found.")
    data = request.get_json(silent=True) or {}
    try:
        item = inventory_item_input_schema.load(data, instance=item, partial=True)
    except ValidationError as exc:
        return jsonify(errors=exc.messages), 422
    db.session.commit()
    return jsonify(inventory_item_schema.dump(item)), 200


@bp.delete("/labs/<int:lab_id>/inventory/<int:item_id>")
@require_lab_role(*_MANAGER_ROLES)
def delete_inventory_item(lab_id: int, item_id: int):
    item = InventoryItem.query.filter_by(id=item_id, lab_id=lab_id).first()
    if not item:
        abort(404, "Inventory item not found.")
    db.session.delete(item)
    db.session.commit()
    return "", 204

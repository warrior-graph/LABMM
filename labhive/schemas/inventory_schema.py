from marshmallow import fields, validate

from labhive.extensions import ma
from labhive.models.inventory import InventoryItem, ItemCondition

VALID_CONDITIONS = [c.value for c in ItemCondition]


class InventoryItemSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = InventoryItem
        load_instance = True
        include_fk = True

    assigned_to = ma.Nested(
        "MemberSchema",
        only=("id", "first_name", "last_name", "email"),
        dump_only=True,
    )


class InventoryItemInputSchema(ma.SQLAlchemySchema):
    class Meta:
        model = InventoryItem
        load_instance = True

    name = ma.auto_field(required=True)
    category = ma.auto_field(required=True)
    description = ma.auto_field()
    serial_number = ma.auto_field()
    quantity = ma.auto_field(load_default=1, required=False)
    condition = ma.auto_field(
        validate=validate.OneOf(VALID_CONDITIONS),
        load_default=ItemCondition.good.value,
        required=False,
    )
    assigned_to_id = ma.auto_field()


inventory_item_schema = InventoryItemSchema()
inventory_items_schema = InventoryItemSchema(many=True)
inventory_item_input_schema = InventoryItemInputSchema()

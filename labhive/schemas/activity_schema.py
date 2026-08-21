from marshmallow import validate

from labhive.extensions import ma
from labhive.models.activity import Activity, ActivityStatus

VALID_STATUSES = [s.value for s in ActivityStatus]


class ActivitySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Activity
        load_instance = True
        include_fk = True

    participants = ma.Nested(
        "MemberSchema", many=True, only=("id", "first_name", "last_name"), dump_only=True
    )
    in_charge = ma.Nested(
        "MemberSchema", many=True, only=("id", "first_name", "last_name"), dump_only=True
    )


class ActivityInputSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Activity
        load_instance = True

    title = ma.auto_field(required=True)
    activity_type = ma.auto_field(required=False)
    description = ma.auto_field()
    venue = ma.auto_field()
    reference_link = ma.auto_field()
    status = ma.auto_field(
        validate=validate.OneOf(VALID_STATUSES),
        load_default=ActivityStatus.planned.value,
        required=False,
    )
    deadline = ma.auto_field()
    completed_at = ma.auto_field()


activity_schema = ActivitySchema()
activities_schema = ActivitySchema(many=True)
activity_input_schema = ActivityInputSchema()

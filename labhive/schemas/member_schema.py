from labhive.extensions import ma
from labhive.models.member import Member
from marshmallow import EXCLUDE


class MemberSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Member
        load_instance = True
        exclude = ("password_hash",)

    # Nested: list of labs this member belongs to (lightweight)
    lab_memberships = ma.Nested(
        "LabMembershipSchema", many=True, exclude=("member",), dump_only=True
    )


class MemberInputSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Member
        load_instance = True
        unknown = EXCLUDE

    first_name = ma.auto_field(required=True)
    last_name = ma.auto_field(required=True)
    email = ma.auto_field(required=True)
    cpf = ma.auto_field(required=True)
    password = ma.String(required=True, load_only=True)


member_schema = MemberSchema()
members_schema = MemberSchema(many=True, exclude=("lab_memberships",))
member_input_schema = MemberInputSchema()

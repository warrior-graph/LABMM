from labhive.extensions import ma
from labhive.models.research import Research


class ResearchSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Research
        load_instance = True
        include_fk = True

    manager = ma.Nested(
        "MemberSchema", exclude=("lab_memberships",), dump_only=True
    )
    members = ma.Nested(
        "MemberSchema", many=True, exclude=("lab_memberships",), dump_only=True
    )
    projects = ma.Nested("ProjectSchema", many=True, exclude=("members",), dump_only=True)


class ResearchInputSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Research
        load_instance = True

    name = ma.auto_field(required=True)
    description = ma.auto_field()
    manager_id = ma.auto_field(load_default=None, allow_none=True)


research_schema = ResearchSchema()
researches_schema = ResearchSchema(many=True, exclude=("members", "projects"))
research_input_schema = ResearchInputSchema()

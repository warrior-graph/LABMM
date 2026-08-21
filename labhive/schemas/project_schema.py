import marshmallow as msh

from labhive.extensions import ma
from labhive.models.project import Project, ProjectStatus


class ProjectSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Project
        load_instance = True
        include_fk = True

    status = msh.fields.Enum(ProjectStatus, by_value=True)
    tech_lead = ma.Nested(
        "MemberSchema", exclude=("lab_memberships",), dump_only=True
    )
    members = ma.Nested(
        "MemberSchema", many=True, exclude=("lab_memberships",), dump_only=True
    )
    research_group = ma.Nested(
        "ResearchSchema", exclude=("members", "projects"), dump_only=True
    )


class ProjectInputSchema(ma.SQLAlchemySchema):
    class Meta:
        model = Project
        load_instance = True

    name = ma.auto_field(required=True)
    description = ma.auto_field()
    status = msh.fields.String(
        load_default=ProjectStatus.planned.value,
        validate=msh.validate.OneOf([s.value for s in ProjectStatus]),
    )
    start_date = ma.auto_field()
    end_date = ma.auto_field()
    research_id = ma.auto_field()
    tech_lead_id = ma.auto_field()


project_schema = ProjectSchema()
projects_schema = ProjectSchema(many=True, exclude=("members", "research_group"))
project_input_schema = ProjectInputSchema()

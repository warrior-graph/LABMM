from labhive.extensions import ma
from labhive.models.role import Role


class RoleSchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Role
        load_instance = False


role_schema = RoleSchema()
roles_schema = RoleSchema(many=True)

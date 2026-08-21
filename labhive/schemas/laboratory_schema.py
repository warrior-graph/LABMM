from labhive.extensions import ma
from labhive.models.laboratory import Laboratory


class LaboratorySchema(ma.SQLAlchemyAutoSchema):
    class Meta:
        model = Laboratory
        load_instance = True


laboratory_schema = LaboratorySchema()
laboratories_schema = LaboratorySchema(many=True)

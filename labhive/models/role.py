from labhive.extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key = db.Column(db.String(64), unique=True, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    level = db.Column(db.Integer, nullable=False)
    is_system = db.Column(db.Boolean, default=False, nullable=False)

    def __repr__(self) -> str:
        return f"<Role key={self.key} level={self.level}>"

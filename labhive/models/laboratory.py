from datetime import datetime, timezone

from labhive.extensions import db


class Laboratory(db.Model):
    __tablename__ = "laboratories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    memberships = db.relationship(
        "LabMembership", back_populates="laboratory", cascade="all, delete-orphan"
    )
    research_groups = db.relationship(
        "Research", back_populates="laboratory", cascade="all, delete-orphan"
    )
    projects = db.relationship(
        "Project", back_populates="laboratory", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "Activity", back_populates="laboratory", cascade="all, delete-orphan"
    )
    inventory_items = db.relationship(
        "InventoryItem", back_populates="laboratory", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Laboratory {self.name}>"

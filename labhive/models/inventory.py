import enum
from datetime import datetime, timezone

from labhive.extensions import db


class ItemCondition(str, enum.Enum):
    new = "new"
    good = "good"
    fair = "fair"
    poor = "poor"
    broken = "broken"


class InventoryItem(db.Model):
    __tablename__ = "inventory_items"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    category = db.Column(db.String(64), nullable=False)  # free-text, e.g. "Raspberry Pi", "Cable"
    description = db.Column(db.Text, nullable=True)
    serial_number = db.Column(db.String(128), nullable=True)
    quantity = db.Column(db.Integer, default=1, nullable=False)
    condition = db.Column(
        db.Enum(ItemCondition), default=ItemCondition.good, nullable=False
    )
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    assigned_to_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    laboratory = db.relationship("Laboratory", back_populates="inventory_items")
    assigned_to = db.relationship("Member", foreign_keys=[assigned_to_id])

    def __repr__(self) -> str:
        return f"<InventoryItem {self.name}>"

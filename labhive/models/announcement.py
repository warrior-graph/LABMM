from datetime import datetime, timezone

from labhive.extensions import db


class Announcement(db.Model):
    """Lab announcement. audience = [] means everyone in the lab; otherwise a list of role keys."""

    __tablename__ = "announcements"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=True)
    author_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    audience = db.Column(db.JSON, nullable=False, default=list)
    is_pinned = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    author = db.relationship("Member", foreign_keys=[author_id])
    laboratory = db.relationship("Laboratory", backref="announcements")

    def __repr__(self) -> str:
        return f"<Announcement {self.title}>"

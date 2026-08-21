from datetime import datetime, timezone

from labhive.extensions import db


class Notification(db.Model):
    """In-app notification for a member."""

    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = db.Column(db.String(64), nullable=False)  # member_pending, member_approved, announcement, activity_deadline, status_changed
    message = db.Column(db.String(256), nullable=False)
    link = db.Column(db.String(256), nullable=True)
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    member = db.relationship("Member", backref="notifications")

    def __repr__(self) -> str:
        return f"<Notification {self.type} for {self.member_id}>"

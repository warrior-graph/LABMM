import secrets
from datetime import datetime, timedelta, timezone

from labhive.extensions import db


class InviteToken(db.Model):
    """Time-limited invite link for joining a laboratory."""

    __tablename__ = "invite_tokens"

    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.String(64), unique=True, nullable=False, index=True)
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_by_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    expires_at = db.Column(db.DateTime, nullable=False)
    used_by_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    used_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    laboratory = db.relationship("Laboratory", backref="invite_tokens")
    created_by = db.relationship("Member", foreign_keys=[created_by_id])
    used_by = db.relationship("Member", foreign_keys=[used_by_id])

    @classmethod
    def generate(cls, lab_id: int, created_by_id: int, days: int = 7) -> "InviteToken":
        return cls(
            token=secrets.token_urlsafe(32),
            lab_id=lab_id,
            created_by_id=created_by_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=days),
        )

    @property
    def is_expired(self) -> bool:
        exp = self.expires_at
        if exp.tzinfo is None:  # SQLite drops tzinfo on load
            exp = exp.replace(tzinfo=timezone.utc)
        return datetime.now(timezone.utc) > exp

    def __repr__(self) -> str:
        return f"<InviteToken {self.token[:8]}…>"

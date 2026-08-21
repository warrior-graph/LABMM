import enum
from datetime import datetime, timezone

from labhive.extensions import db

activity_participants = db.Table(
    "activity_participants",
    db.Column(
        "member_id",
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "activity_id",
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)

activity_in_charge = db.Table(
    "activity_in_charge",
    db.Column(
        "member_id",
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "activity_id",
        db.Integer,
        db.ForeignKey("activities.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ActivityStatus(str, enum.Enum):
    planned = "planned"
    in_progress = "in_progress"
    on_hold = "on_hold"
    under_review = "under_review"
    accepted = "accepted"
    rejected = "rejected"
    completed = "completed"
    cancelled = "cancelled"


class Activity(db.Model):
    __tablename__ = "activities"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(256), nullable=False)
    activity_type = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text, nullable=True)
    venue = db.Column(db.String(256), nullable=True)
    reference_link = db.Column(db.String(256), nullable=True)
    status = db.Column(db.Enum(ActivityStatus), default=ActivityStatus.planned, nullable=False)
    deadline = db.Column(db.Date, nullable=True)
    completed_at = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    laboratory = db.relationship("Laboratory", back_populates="activities")
    participants = db.relationship(
        "Member", secondary=activity_participants, backref="activities_participated"
    )
    in_charge = db.relationship(
        "Member", secondary=activity_in_charge, backref="activities_in_charge"
    )

    def __repr__(self) -> str:
        return f"<Activity {self.title}>"

import enum
from datetime import datetime, timezone

from labhive.extensions import db

member_projects = db.Table(
    "member_projects",
    db.Column(
        "member_id",
        db.Integer,
        db.ForeignKey("members.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "project_id",
        db.Integer,
        db.ForeignKey("projects.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class ProjectStatus(str, enum.Enum):
    planned = "planned"
    active = "active"
    completed = "completed"
    cancelled = "cancelled"


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text, nullable=True)
    status = db.Column(
        db.Enum(ProjectStatus), default=ProjectStatus.planned, nullable=False
    )
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    research_id = db.Column(
        db.Integer,
        db.ForeignKey("research_groups.id", ondelete="SET NULL"),
        nullable=True,
    )
    tech_lead_id = db.Column(
        db.Integer,
        db.ForeignKey("members.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    laboratory = db.relationship("Laboratory", back_populates="projects")
    research_group = db.relationship("Research", back_populates="projects")
    tech_lead = db.relationship("Member", foreign_keys=[tech_lead_id])
    members = db.relationship(
        "Member", secondary="member_projects", back_populates="projects"
    )

    def __repr__(self) -> str:
        return f"<Project {self.name}>"

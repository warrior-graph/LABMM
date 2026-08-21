import enum
from datetime import datetime, timezone

from labhive.extensions import db


class LabRole(str, enum.Enum):
    lab_coordinator = "lab_coordinator"        # Professor responsible for the lab
    engineering_manager = "engineering_manager"
    project_manager = "project_manager"
    chief_scientist = "chief_scientist"        # Renamed from research_manager
    tech_lead = "tech_lead"
    engineer = "engineer"
    researcher = "researcher"
    research_fellow = "research_fellow"        # Junior researcher / student
    staff = "staff"


# Roles that can manage lab membership
MANAGER_ROLES = frozenset({
    LabRole.lab_coordinator,
    LabRole.engineering_manager,
    LabRole.project_manager,
    LabRole.chief_scientist,
})

# Hierarchy level — lower number = more authority
ROLE_LEVEL: dict[LabRole, int] = {
    LabRole.lab_coordinator: 0,
    LabRole.engineering_manager: 1,
    LabRole.project_manager: 1,
    LabRole.chief_scientist: 1,
    LabRole.tech_lead: 2,
    LabRole.engineer: 3,
    LabRole.researcher: 3,
    LabRole.research_fellow: 3,
    LabRole.staff: 4,
}


class CompensationType(str, enum.Enum):
    project_salary = "project_salary"
    research_grant = "research_grant"
    volunteer = "volunteer"


class LabMembership(db.Model):
    __tablename__ = "lab_memberships"

    member_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="CASCADE"), primary_key=True
    )
    lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    roles = db.Column(db.JSON, nullable=False, default=list)
    specialization = db.Column(db.String(64), nullable=True)
    joined_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    compensation_type = db.Column(db.Enum(CompensationType), nullable=True)
    compensation_value = db.Column(db.Numeric(10, 2), nullable=True)
    reports_to_id = db.Column(
        db.Integer, db.ForeignKey("members.id", ondelete="SET NULL"), nullable=True
    )
    left_at = db.Column(db.DateTime, nullable=True)  # set when the member leaves the lab

    # Relationships
    member = db.relationship(
        "Member", foreign_keys="[LabMembership.member_id]", back_populates="lab_memberships"
    )
    laboratory = db.relationship("Laboratory", back_populates="memberships")
    reports_to = db.relationship("Member", foreign_keys="[LabMembership.reports_to_id]")

    @property
    def primary_role(self) -> str:
        """Return the highest-authority role (lowest ROLE_LEVEL number)."""
        if not self.roles:
            return ""
        return min(self.roles, key=lambda r: ROLE_LEVEL.get(r, 99))

    def __repr__(self) -> str:
        return f"<LabMembership member={self.member_id} lab={self.lab_id} roles={self.roles}>"

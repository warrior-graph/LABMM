from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from labhive.extensions import db


class Member(db.Model):
    __tablename__ = "members"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(64), nullable=False)
    last_name = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(128), unique=True, nullable=False, index=True)
    cpf = db.Column(db.String(11), unique=True, nullable=True, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False, nullable=False)
    is_professor = db.Column(db.Boolean, default=False, nullable=False)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    desired_lab_id = db.Column(
        db.Integer,
        db.ForeignKey("laboratories.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    desired_lab = db.relationship(
        "Laboratory", foreign_keys=[desired_lab_id], backref=db.backref("pending_members", lazy="dynamic")
    )
    lab_memberships = db.relationship(
        "LabMembership",
        foreign_keys="[LabMembership.member_id]",
        back_populates="member",
        cascade="all, delete-orphan",
    )
    research_groups = db.relationship(
        "Research", secondary="member_research", back_populates="members"
    )
    projects = db.relationship(
        "Project", secondary="member_projects", back_populates="members"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def __repr__(self) -> str:
        return f"<Member {self.email}>"

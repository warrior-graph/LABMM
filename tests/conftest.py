import pytest
from flask_jwt_extended import create_access_token

from labhive import create_app
from labhive.extensions import db as _db
from labhive.models.lab_membership import LabMembership, LabRole, ROLE_LEVEL
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.role import Role


@pytest.fixture(scope="session")
def app():
    app = create_app("testing")
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def db_tables(app):
    """Create all tables before each test and drop them after."""
    with app.app_context():
        _db.create_all()
        for role_key, level in ROLE_LEVEL.items():
            if not Role.query.filter_by(key=role_key.value).first():
                _db.session.add(Role(key=role_key.value, name=role_key.value, level=level, is_system=True))
        _db.session.commit()
        yield _db
        _db.session.remove()
        _db.drop_all()


# ── helpers ──────────────────────────────────────────────────────────────────

def _make_member(app, first="Test", last="User", email="test@lab.local",
                 password="password123", is_super_admin=False, cpf=None,
                 is_professor=False):
    with app.app_context():
        m = Member(first_name=first, last_name=last, email=email,
                   is_super_admin=is_super_admin, is_professor=is_professor,
                   is_approved=True, cpf=cpf)
        m.set_password(password)
        _db.session.add(m)
        _db.session.commit()
        return m.id


def _token_headers(app, member_id):
    with app.app_context():
        member = _db.session.get(Member, member_id)
        token = create_access_token(
            identity=str(member.id),
            additional_claims={
                "is_super_admin": member.is_super_admin,
                "is_professor": member.is_professor,
            },
        )
        return {"Authorization": f"Bearer {token}"}


# ── global fixtures ───────────────────────────────────────────────────────────

@pytest.fixture()
def super_admin(app, db_tables):
    mid = _make_member(app, first="Admin", last="Super",
                       email="admin@lab.local", is_super_admin=True,
                       cpf="00000000001")
    return mid


@pytest.fixture()
def sa_headers(app, super_admin):
    return _token_headers(app, super_admin)


@pytest.fixture()
def lab(app, db_tables, super_admin):
    with app.app_context():
        laboratory = Laboratory(name="Test Lab", description="A test laboratory")
        _db.session.add(laboratory)
        _db.session.commit()
        return laboratory.id


@pytest.fixture()
def manager(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Manager",
                       email="manager@lab.local", cpf="00000000002")
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.engineering_manager])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def engineer(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Engineer",
                       email="engineer@lab.local", cpf="00000000003")
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.engineer])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def researcher(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Researcher",
                       email="researcher@lab.local", cpf="00000000004")
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.researcher])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def chief_scientist(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Scientist",
                       email="scientist@lab.local", cpf="00000000005")
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.chief_scientist])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def ceo(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Coordinator",
                       email="coordinator@lab.local", cpf="00000000006",
                       is_professor=True)
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.lab_coordinator])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def staff(app, db_tables, lab):
    mid = _make_member(app, first="Lab", last="Staff",
                       email="staff@lab.local", cpf="00000000007")
    with app.app_context():
        membership = LabMembership(member_id=mid, lab_id=lab,
                                   roles=[LabRole.staff])
        _db.session.add(membership)
        _db.session.commit()
    return mid


@pytest.fixture()
def mgr_headers(app, manager):
    return _token_headers(app, manager)


@pytest.fixture()
def cs_headers(app, chief_scientist):
    return _token_headers(app, chief_scientist)


@pytest.fixture()
def ceo_headers(app, ceo):
    return _token_headers(app, ceo)


@pytest.fixture()
def eng_headers(app, engineer):
    return _token_headers(app, engineer)


@pytest.fixture()
def res_headers(app, researcher):
    return _token_headers(app, researcher)


@pytest.fixture()
def stf_headers(app, staff):
    return _token_headers(app, staff)

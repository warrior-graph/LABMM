import pytest
from sqlalchemy.exc import IntegrityError

from labhive.extensions import db
from labhive.models.member import Member


def test_set_password_hashes(app, db_tables):
    with app.app_context():
        m = Member(first_name="Alice", last_name="Smith", email="alice@lab.local")
        m.set_password("secret123")
        assert m.password_hash != "secret123"
        assert m.password_hash is not None


def test_check_password_correct(app, db_tables):
    with app.app_context():
        m = Member(first_name="Bob", last_name="Jones", email="bob@lab.local")
        m.set_password("mypassword")
        assert m.check_password("mypassword") is True


def test_check_password_wrong(app, db_tables):
    with app.app_context():
        m = Member(first_name="Carol", last_name="Brown", email="carol@lab.local")
        m.set_password("correct")
        assert m.check_password("wrong") is False


def test_is_super_admin_defaults_false(app, db_tables):
    with app.app_context():
        m = Member(first_name="Dave", last_name="Lee", email="dave@lab.local")
        m.set_password("pass")
        db.session.add(m)
        db.session.commit()
        assert m.is_super_admin is False


def test_email_uniqueness(app, db_tables):
    with app.app_context():
        m1 = Member(first_name="Eve", last_name="A", email="dup@lab.local")
        m1.set_password("pass")
        m2 = Member(first_name="Eve", last_name="B", email="dup@lab.local")
        m2.set_password("pass")
        db.session.add(m1)
        db.session.commit()
        db.session.add(m2)
        with pytest.raises(IntegrityError):
            db.session.commit()

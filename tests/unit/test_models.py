from labhive.extensions import db
from labhive.models.activity import Activity
from labhive.models.lab_membership import LabMembership, LabRole
from labhive.models.laboratory import Laboratory
from labhive.models.member import Member
from labhive.models.project import Project
from labhive.models.research import Research


def _add(app, obj):
    with app.app_context():
        db.session.add(obj)
        db.session.commit()
        return obj


def test_cascade_delete_lab_removes_research(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="CascadeLab")
        db.session.add(lab)
        db.session.commit()
        group = Research(name="Group A", lab_id=lab.id)
        db.session.add(group)
        db.session.commit()
        lab_id = lab.id
        group_id = group.id

        db.session.delete(lab)
        db.session.commit()

        assert db.session.get(Research, group_id) is None


def test_cascade_delete_lab_removes_projects(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="CascadeLab2")
        db.session.add(lab)
        db.session.commit()
        project = Project(name="Proj A", lab_id=lab.id)
        db.session.add(project)
        db.session.commit()
        project_id = project.id

        db.session.delete(lab)
        db.session.commit()

        assert db.session.get(Project, project_id) is None


def test_cascade_delete_lab_removes_activities(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="CascadeLab3")
        db.session.add(lab)
        db.session.commit()
        activity = Activity(title="Activity A", lab_id=lab.id)
        db.session.add(activity)
        db.session.commit()
        activity_id = activity.id

        db.session.delete(lab)
        db.session.commit()

        assert db.session.get(Activity, activity_id) is None


def test_cascade_delete_lab_removes_memberships(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="CascadeLab4")
        db.session.add(lab)
        member = Member(first_name="X", last_name="Y", email="xy@lab.local")
        member.set_password("p")
        db.session.add(member)
        db.session.commit()
        membership = LabMembership(member_id=member.id, lab_id=lab.id, roles=[LabRole.staff])
        db.session.add(membership)
        db.session.commit()
        lab_id = lab.id
        member_id = member.id

        db.session.delete(lab)
        db.session.commit()

        assert (
            LabMembership.query.filter_by(member_id=member_id, lab_id=lab_id).first() is None
        )


def test_member_research_association(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="AssocLab")
        db.session.add(lab)
        member = Member(first_name="A", last_name="B", email="ab@lab.local")
        member.set_password("p")
        db.session.add(member)
        db.session.commit()
        group = Research(name="Assoc Group", lab_id=lab.id)
        db.session.add(group)
        db.session.commit()

        group.members.append(member)
        db.session.commit()

        refreshed = db.session.get(Research, group.id)
        assert member in refreshed.members


def test_activity_participant_association(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="ActivityLab")
        db.session.add(lab)
        member = Member(first_name="C", last_name="D", email="cd@lab.local")
        member.set_password("p")
        db.session.add(member)
        db.session.commit()
        activity = Activity(title="Test Activity", lab_id=lab.id)
        db.session.add(activity)
        db.session.commit()

        activity.participants.append(member)
        db.session.commit()

        refreshed = db.session.get(Activity, activity.id)
        assert member in refreshed.participants


def test_activity_in_charge_association(app, db_tables):
    with app.app_context():
        lab = Laboratory(name="InChargeLab")
        db.session.add(lab)
        member = Member(first_name="E", last_name="F", email="ef@lab.local")
        member.set_password("p")
        db.session.add(member)
        db.session.commit()
        activity = Activity(title="Managed Activity", lab_id=lab.id)
        db.session.add(activity)
        db.session.commit()

        activity.in_charge.append(member)
        db.session.commit()

        refreshed = db.session.get(Activity, activity.id)
        assert member in refreshed.in_charge

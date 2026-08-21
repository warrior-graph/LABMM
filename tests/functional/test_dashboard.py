from datetime import date, datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()

# ── Auth ─────────────────────────────────────────────────────────────────────


def test_dashboard_requires_auth(client, db_tables):
    resp = client.get("/dashboard/summary")
    assert resp.status_code == 401


# ── Super-admin view ─────────────────────────────────────────────────────────


def test_super_admin_dashboard_summary(
    client, db_tables, lab, sa_headers, super_admin
):
    # Approved, active members with membership in the lab
    r1 = client.post(
        "/auth/register",
        json={
            "first_name": "Ana",
            "last_name": "Silva",
            "email": "ana@x.local",
            "password": "pass123",
            "cpf": "11122233344",
        },
        headers=sa_headers,
    )
    member_a = r1.get_json()["member"]
    client.post(
        f"/labs/{lab}/members",
        json={"member_id": member_a["id"], "roles": ["engineer"]},
        headers=sa_headers,
    )

    r2 = client.post(
        "/auth/register",
        json={
            "first_name": "Bruno",
            "last_name": "Lima",
            "email": "bruno@x.local",
            "password": "pass123",
            "cpf": "11122233355",
        },
        headers=sa_headers,
    )
    member_b = r2.get_json()["member"]
    client.post(
        f"/labs/{lab}/members",
        json={"member_id": member_b["id"], "roles": ["researcher"]},
        headers=sa_headers,
    )

    # Pending member (self-registration without token → is_approved=False)
    pending = client.post(
        "/auth/register",
        json={
            "first_name": "Carla",
            "last_name": "Souza",
            "email": "carla@x.local",
            "password": "pass123",
            "cpf": "11122233366",
            "desired_lab_id": lab,
        },
    ).get_json()["member"]
    assert pending["is_approved"] is False

    # Activities in various statuses
    client.post(
        f"/labs/{lab}/activities",
        json={"title": "Act In Progress", "status": "in_progress"},
        headers=sa_headers,
    )
    client.post(
        f"/labs/{lab}/activities",
        json={"title": "Act Under Review", "status": "under_review"},
        headers=sa_headers,
    )
    client.post(
        f"/labs/{lab}/activities",
        json={"title": "Act Completed", "status": "completed"},
        headers=sa_headers,
    )
    # Activity with a deadline for upcoming_deadlines
    client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Act With Deadline",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=3)).isoformat(),
        },
        headers=sa_headers,
    )

    # Active project (and one with end_date)
    client.post(
        f"/labs/{lab}/projects",
        json={"name": "Active Project", "status": "active"},
        headers=sa_headers,
    )
    client.post(
        f"/labs/{lab}/projects",
        json={
            "name": "Project With End",
            "status": "active",
            "end_date": (TODAY + timedelta(days=10)).isoformat(),
        },
        headers=sa_headers,
    )

    # Inventory items
    client.post(
        f"/labs/{lab}/inventory",
        json={"name": "Raspberry Pi", "category": "Hardware"},
        headers=sa_headers,
    )
    client.post(
        f"/labs/{lab}/inventory",
        json={"name": "Osciloscope", "category": "Hardware"},
        headers=sa_headers,
    )

    resp = client.get("/dashboard/summary", headers=sa_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["is_manager"] is True

    counts = data["counts"]
    assert counts["active_members"] == 2
    assert counts["pending_members"] == 1
    assert counts["activities_in_progress"] == 2  # one plain + one with deadline
    assert counts["activities_under_review"] == 1
    assert counts["activities_completed"] == 1
    assert counts["projects_active"] == 2
    assert counts["inventory_items"] == 2

    # pending_members list
    assert len(data["pending_members"]) == 1
    pm = data["pending_members"][0]
    assert pm["member_id"] == pending["id"]
    assert pm["first_name"] == "Carla"
    assert pm["last_name"] == "Souza"
    assert pm["email"] == "carla@x.local"
    assert pm["desired_lab_id"] == lab
    assert pm["lab_name"] == "Test Lab"
    assert pm["created_at"]

    # upcoming_deadlines: the two entries, sorted by due_on asc, limit 10
    deadlines = data["upcoming_deadlines"]
    assert len(deadlines) == 2
    assert [d["due_on"] for d in deadlines] == sorted(
        d["due_on"] for d in deadlines
    )
    act_deadline = next(d for d in deadlines if d["type"] == "activity")
    assert act_deadline["title"] == "Act With Deadline"
    assert act_deadline["status"] == "in_progress"
    assert act_deadline["lab_id"] == lab
    assert act_deadline["lab_name"] == "Test Lab"
    assert act_deadline["due_on"] == (TODAY + timedelta(days=3)).isoformat()
    assert act_deadline["days_left"] == 3
    assert act_deadline["overdue"] is False

    proj_deadline = next(d for d in deadlines if d["type"] == "project")
    assert proj_deadline["title"] == "Project With End"
    assert proj_deadline["due_on"] == (TODAY + timedelta(days=10)).isoformat()
    assert proj_deadline["days_left"] == 10
    assert proj_deadline["overdue"] is False

    # recent_activities: newest first, max 5
    recent = data["recent_activities"]
    assert len(recent) == 4
    created_ats = [a["created_at"] for a in recent]
    assert created_ats == sorted(created_ats, reverse=True)

    # manager view has no my_* data
    assert data["my_activities"] == []
    assert data["my_projects"] == []
    assert data["my_deadlines"] == []


# ── Regular member view ──────────────────────────────────────────────────────


def test_regular_member_dashboard_summary(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    # A non-manager member (engineer) — create an activity where they
    # participate / are in charge, and a project where they are a member.
    activity = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "My Activity",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=7)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/activities/{activity['id']}/participants",
        json={"member_id": engineer},
        headers=sa_headers,
    )
    client.post(
        f"/labs/{lab}/activities/{activity['id']}/in_charge",
        json={"member_id": engineer},
        headers=sa_headers,
    )

    project = client.post(
        f"/labs/{lab}/projects",
        json={
            "name": "My Project",
            "status": "active",
            "end_date": (TODAY + timedelta(days=20)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/projects/{project['id']}/members",
        json={"member_id": engineer},
        headers=sa_headers,
    )

    resp = client.get("/dashboard/summary", headers=eng_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["is_manager"] is False

    # All manager counts zero
    assert data["counts"] == {
        "active_members": 0,
        "pending_members": 0,
        "activities_in_progress": 0,
        "activities_under_review": 0,
        "activities_completed": 0,
        "projects_active": 0,
        "inventory_items": 0,
    }
    assert data["pending_members"] == []
    assert data["upcoming_deadlines"] == []
    assert data["recent_activities"] == []

    # my_activities
    assert len(data["my_activities"]) == 1
    ma = data["my_activities"][0]
    assert ma["id"] == activity["id"]
    assert ma["title"] == "My Activity"
    assert ma["status"] == "in_progress"
    assert ma["lab_id"] == lab
    assert ma["lab_name"] == "Test Lab"
    assert ma["deadline"] == (TODAY + timedelta(days=7)).isoformat()
    assert ma["days_left"] == 7

    # my_projects
    assert len(data["my_projects"]) == 1
    mp = data["my_projects"][0]
    assert mp["id"] == project["id"]
    assert mp["name"] == "My Project"
    assert mp["status"] == "active"
    assert mp["lab_id"] == lab
    assert mp["lab_name"] == "Test Lab"
    assert mp["end_date"] == (TODAY + timedelta(days=20)).isoformat()

    # my_deadlines — activity + project, sorted by due_on asc
    assert len(data["my_deadlines"]) == 2
    md = data["my_deadlines"]
    assert [d["due_on"] for d in md] == sorted(d["due_on"] for d in md)
    assert md[0]["type"] == "activity"
    assert md[0]["days_left"] == 7
    assert md[1]["type"] == "project"
    assert md[1]["days_left"] == 20


# ── Manager (non-super-admin) view ───────────────────────────────────────────


def test_manager_dashboard_summary(
    client, db_tables, lab, super_admin, sa_headers, manager, mgr_headers
):
    # A manager (engineering_manager) sees manager fields but no my_*
    client.post(
        f"/labs/{lab}/activities",
        json={"title": "Manager Act", "status": "in_progress"},
        headers=sa_headers,
    )
    resp = client.get("/dashboard/summary", headers=mgr_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["is_manager"] is True
    assert data["counts"]["activities_in_progress"] == 1
    assert data["recent_activities"]
    # Pending members require super-admin or professor — manager alone sees none
    assert data["pending_members"] == []
    assert data["counts"]["pending_members"] == 0
    assert data["my_activities"] == []
    assert data["my_projects"] == []
    assert data["my_deadlines"] == []


# ── Global list endpoints (dashboard/activities, /projects, /inventory) ─────


def test_dashboard_activities_list(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    a1 = client.post(
        f"/labs/{lab}/activities",
        json={"title": "A1", "status": "in_progress"},
        headers=sa_headers,
    ).get_json()
    a2 = client.post(
        f"/labs/{lab}/activities",
        json={"title": "A2", "status": "completed"},
        headers=sa_headers,
    ).get_json()

    # Manager sees all activities; ?status= filters
    resp = client.get("/dashboard/activities", headers=sa_headers)
    assert resp.status_code == 200
    assert {a["title"] for a in resp.get_json()} == {"A1", "A2"}

    resp = client.get("/dashboard/activities?status=in_progress", headers=sa_headers)
    assert [a["title"] for a in resp.get_json()] == ["A1"]

    resp = client.get("/dashboard/activities?status=bogus", headers=sa_headers)
    assert resp.status_code == 422

    # Member sees nothing until they join an activity
    resp = client.get("/dashboard/activities", headers=eng_headers)
    assert resp.get_json() == []

    client.post(
        f"/labs/{lab}/activities/{a1['id']}/in_charge",
        json={"member_id": engineer},
        headers=sa_headers,
    )
    resp = client.get("/dashboard/activities", headers=eng_headers)
    assert [a["id"] for a in resp.get_json()] == [a1["id"]]
    assert resp.get_json()[0]["lab_name"] == "Test Lab"


def test_dashboard_projects_list(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    p1 = client.post(
        f"/labs/{lab}/projects",
        json={"name": "P1", "status": "active"},
        headers=sa_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/projects",
        json={"name": "P2", "status": "planned"},
        headers=sa_headers,
    ).get_json()

    resp = client.get("/dashboard/projects?status=active", headers=sa_headers)
    assert resp.status_code == 200
    assert [p["name"] for p in resp.get_json()] == ["P1"]

    resp = client.get("/dashboard/projects", headers=eng_headers)
    assert resp.get_json() == []

    client.post(
        f"/labs/{lab}/projects/{p1['id']}/members",
        json={"member_id": engineer},
        headers=sa_headers,
    )
    resp = client.get("/dashboard/projects", headers=eng_headers)
    assert [p["id"] for p in resp.get_json()] == [p1["id"]]
    assert resp.get_json()[0]["lab_name"] == "Test Lab"


def test_dashboard_inventory_list(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    client.post(
        f"/labs/{lab}/inventory",
        json={"name": "RPi", "category": "HW"},
        headers=sa_headers,
    )
    osc = client.post(
        f"/labs/{lab}/inventory",
        json={"name": "Osc", "category": "HW", "assigned_to_id": engineer},
        headers=sa_headers,
    ).get_json()

    resp = client.get("/dashboard/inventory", headers=sa_headers)
    assert resp.status_code == 200
    assert len(resp.get_json()) == 2

    # Member sees only items assigned to them
    resp = client.get("/dashboard/inventory", headers=eng_headers)
    items = resp.get_json()
    assert len(items) == 1
    assert items[0]["id"] == osc["id"]
    assert items[0]["name"] == "Osc"
    assert items[0]["assigned_to_id"] == engineer
    assert items[0]["lab_name"] == "Test Lab"

from datetime import datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()


# ── Calendar events ─────────────────────────────────────────────────────────


def test_calendar_requires_auth(client, db_tables):
    resp = client.get("/calendar")
    assert resp.status_code == 401


def test_calendar_manager_sees_lab_events(
    client, db_tables, lab, super_admin, sa_headers
):
    deadline = TODAY + timedelta(days=5)
    activity = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Cal Act",
            "status": "under_review",
            "deadline": deadline.isoformat(),
        },
        headers=sa_headers,
    ).get_json()

    end_date = TODAY + timedelta(days=40)
    project = client.post(
        f"/labs/{lab}/projects",
        json={
            "name": "Cal Project",
            "status": "active",
            "end_date": end_date.isoformat(),
        },
        headers=sa_headers,
    ).get_json()

    # All dated events
    resp = client.get("/calendar", headers=sa_headers)
    assert resp.status_code == 200
    events = resp.get_json()
    assert {e["id"] for e in events if e["type"] == "activity"} == {activity["id"]}
    assert {e["id"] for e in events if e["type"] == "project"} == {project["id"]}
    act = next(e for e in events if e["type"] == "activity")
    assert act["title"] == "Cal Act"
    assert act["status"] == "under_review"
    assert act["lab_id"] == lab
    assert act["lab_name"] == "Test Lab"
    assert act["date"] == deadline.isoformat()

    # Month filter — activity month includes it, project month excludes it
    month = deadline.strftime("%Y-%m")
    resp = client.get(f"/calendar?month={month}", headers=sa_headers)
    events = resp.get_json()
    assert [e["type"] for e in events] == ["activity"]
    assert events[0]["date"].startswith(month)

    # Invalid month format
    resp = client.get("/calendar?month=2026-13-99", headers=sa_headers)
    assert resp.status_code == 422


def test_calendar_member_sees_only_own(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    other = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Other Act",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=2)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()

    mine = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "My Cal Act",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=3)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/activities/{mine['id']}/in_charge",
        json={"member_id": engineer},
        headers=sa_headers,
    )

    resp = client.get("/calendar", headers=eng_headers)
    events = resp.get_json()
    assert [e["id"] for e in events] == [mine["id"]]
    assert other["id"] not in [e["id"] for e in events]


# ── ?window= filter on /dashboard/activities ────────────────────────────────


def test_dashboard_activities_window_filter(
    client, db_tables, lab, super_admin, sa_headers
):
    today_act = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Due Today", "status": "in_progress", "deadline": TODAY.isoformat()},
        headers=sa_headers,
    ).get_json()
    week_act = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Due In Week",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=5)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    far_act = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Due Far",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=60)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    no_deadline = client.post(
        f"/labs/{lab}/activities",
        json={"title": "No Deadline", "status": "in_progress"},
        headers=sa_headers,
    ).get_json()

    resp = client.get("/dashboard/activities?window=today", headers=sa_headers)
    assert [a["id"] for a in resp.get_json()] == [today_act["id"]]

    resp = client.get("/dashboard/activities?window=week", headers=sa_headers)
    ids = {a["id"] for a in resp.get_json()}
    assert ids == {today_act["id"], week_act["id"]}

    resp = client.get("/dashboard/activities?window=month", headers=sa_headers)
    ids = {a["id"] for a in resp.get_json()}
    assert ids == {today_act["id"], week_act["id"]}
    assert far_act["id"] not in ids
    assert no_deadline["id"] not in ids

    resp = client.get("/dashboard/activities?window=bogus", headers=sa_headers)
    assert resp.status_code == 422


# ── Review workflow (under_review -> accepted/rejected) ─────────────────────


def test_review_activity(
    client, db_tables, lab, super_admin, sa_headers, manager, mgr_headers, engineer, eng_headers
):
    activity = client.post(
        f"/labs/{lab}/activities",
        json={"title": "To Review", "status": "under_review"},
        headers=sa_headers,
    ).get_json()

    # Manager (engineering_manager) can accept
    resp = client.post(
        f"/labs/{lab}/activities/{activity['id']}/review",
        json={"decision": "accepted"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "accepted"
    assert resp.get_json()["completed_at"] is not None

    # A second review is rejected (status no longer under_review)
    resp = client.post(
        f"/labs/{lab}/activities/{activity['id']}/review",
        json={"decision": "rejected"},
        headers=mgr_headers,
    )
    assert resp.status_code == 409

    # Reject flow
    act2 = client.post(
        f"/labs/{lab}/activities",
        json={"title": "To Reject", "status": "under_review"},
        headers=sa_headers,
    ).get_json()
    resp = client.post(
        f"/labs/{lab}/activities/{act2['id']}/review",
        json={"decision": "rejected"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "rejected"
    assert resp.get_json()["completed_at"] is None

    # Invalid decision
    act3 = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Invalid", "status": "under_review"},
        headers=sa_headers,
    ).get_json()
    resp = client.post(
        f"/labs/{lab}/activities/{act3['id']}/review",
        json={"decision": "maybe"},
        headers=mgr_headers,
    )
    assert resp.status_code == 422

    # Regular member cannot review
    act4 = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Member No", "status": "under_review"},
        headers=sa_headers,
    ).get_json()
    resp = client.post(
        f"/labs/{lab}/activities/{act4['id']}/review",
        json={"decision": "accepted"},
        headers=eng_headers,
    )
    assert resp.status_code == 403

from datetime import datetime, timedelta, timezone

TODAY = datetime.now(timezone.utc).date()


def test_register_triggers_pending_notification(
    client, db_tables, lab, manager, mgr_headers
):
    client.post(
        "/auth/register",
        json={
            "first_name": "Nova",
            "last_name": "Membro",
            "email": "nova@x.local",
            "password": "pass123",
            "cpf": "12345678901",
            "desired_lab_id": lab,
        },
    )
    resp = client.get("/notifications", headers=mgr_headers)
    assert resp.status_code == 200
    msgs = [n["message"] for n in resp.get_json() if n["type"] == "member_pending"]
    assert any("Nova Membro" in m for m in msgs)

    resp = client.get("/notifications/unread-count", headers=mgr_headers)
    assert resp.get_json()["count"] >= 1


def test_approve_triggers_member_notification(
    client, db_tables, lab, super_admin, sa_headers
):
    member = client.post(
        "/auth/register",
        json={
            "first_name": "Pendente",
            "last_name": "Aprov",
            "email": "pend@x.local",
            "password": "pass123",
            "cpf": "12345678902",
            "desired_lab_id": lab,
        },
    ).get_json()["member"]
    client.post(f"/members/{member['id']}/approve", headers=sa_headers)

    # The notification goes to the approved member, not to the approver
    login = client.post(
        "/auth/login",
        json={"email": "pend@x.local", "password": "pass123"},
    )
    assert login.status_code == 200
    member_token = login.get_json()["access_token"]
    headers = {"Authorization": f"Bearer {member_token}"}

    resp = client.get("/notifications", headers=headers)
    assert resp.status_code == 200
    approved = [
        n for n in resp.get_json()
        if n["type"] == "member_approved" and "aprovada" in n["message"]
    ]
    assert len(approved) == 1


def test_announcement_triggers_notification(
    client, db_tables, lab, super_admin, sa_headers, manager, mgr_headers, engineer, eng_headers
):
    client.post(
        "/announcements",
        json={"lab_id": lab, "title": "Aviso importante", "body": "Corpo"},
        headers=mgr_headers,
    )
    resp = client.get("/notifications", headers=eng_headers)
    assert resp.status_code == 200
    anns = [n for n in resp.get_json() if n["type"] == "announcement"]
    assert any(n["message"] == "Aviso importante" for n in anns)

    # Mark read + unread count + read-all
    nid = anns[0]["id"]
    resp = client.post(f"/notifications/{nid}/read", headers=eng_headers)
    assert resp.status_code == 200
    assert resp.get_json()["is_read"] is True
    resp = client.get("/notifications/unread-count", headers=eng_headers)
    before = resp.get_json()["count"]

    client.post(
        "/announcements",
        json={"lab_id": lab, "title": "Outro aviso"},
        headers=mgr_headers,
    )
    resp = client.post("/notifications/read-all", headers=eng_headers)
    assert resp.status_code == 200
    resp = client.get("/notifications/unread-count", headers=eng_headers)
    assert resp.get_json()["count"] == 0
    assert before >= 0  # sanity


def test_deadline_sync_notifications(
    client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers
):
    act = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Prazo próximo",
            "status": "in_progress",
            "deadline": (TODAY + timedelta(days=7)).isoformat(),
        },
        headers=sa_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/activities/{act['id']}/in_charge",
        json={"member_id": engineer},
        headers=sa_headers,
    )

    # First fetch creates the deadline notification (lazy sync)
    resp = client.get("/notifications", headers=eng_headers)
    deadlines = [
        n for n in resp.get_json()
        if n["type"] == "activity_deadline" and n["message"].startswith("Prazo em 7 dias")
    ]
    assert len(deadlines) == 1
    assert deadlines[0]["link"] == f"/labs/{lab}/activities/{act['id']}"

    # Second fetch does not duplicate (dedupe)
    resp = client.get("/notifications", headers=eng_headers)
    deadlines = [
        n for n in resp.get_json()
        if n["type"] == "activity_deadline" and n["message"].startswith("Prazo em 7 dias")
    ]
    assert len(deadlines) == 1

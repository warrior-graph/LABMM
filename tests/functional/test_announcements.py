# ── Announcements ────────────────────────────────────────────────────────────


def test_announcement_crud_and_visibility(
    client, db_tables, lab, super_admin, sa_headers, manager, mgr_headers, engineer, eng_headers
):
    # Manager creates an announcement for everyone in the lab
    resp = client.post(
        "/announcements",
        json={"lab_id": lab, "title": "Reunião semanal", "body": "Segunda às 10h.", "is_pinned": True},
        headers=mgr_headers,
    )
    assert resp.status_code == 201
    ann = resp.get_json()
    assert ann["title"] == "Reunião semanal"
    assert ann["lab_name"] == "Test Lab"
    assert ann["is_pinned"] is True
    assert ann["author_name"]

    # Member of the lab can see it
    resp = client.get("/announcements", headers=eng_headers)
    assert resp.status_code == 200
    assert [a["id"] for a in resp.get_json()] == [ann["id"]]

    # pinned_only filter
    resp = client.get("/announcements?pinned_only=1", headers=eng_headers)
    assert [a["id"] for a in resp.get_json()] == [ann["id"]]

    # Non-manager cannot create
    resp = client.post(
        "/announcements",
        json={"lab_id": lab, "title": "Nope"},
        headers=eng_headers,
    )
    assert resp.status_code == 403

    # Role-targeted audience: engineer sees it, a member without the role does not
    resp = client.post(
        "/announcements",
        json={"lab_id": lab, "title": "Só para staff", "audience": ["staff"]},
        headers=mgr_headers,
    )
    assert resp.status_code == 201
    staff_ann = resp.get_json()
    resp = client.get("/announcements", headers=eng_headers)
    assert staff_ann["id"] not in [a["id"] for a in resp.get_json()]

    # Update by manager
    resp = client.put(
        f"/announcements/{ann['id']}",
        json={"title": "Reunião semanal atualizada"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Reunião semanal atualizada"

    # Member cannot update
    resp = client.put(
        f"/announcements/{ann['id']}",
        json={"title": "Hack"},
        headers=eng_headers,
    )
    assert resp.status_code == 403

    # Delete by manager
    resp = client.delete(f"/announcements/{ann['id']}", headers=mgr_headers)
    assert resp.status_code == 204
    resp = client.get("/announcements", headers=eng_headers)
    assert ann["id"] not in [a["id"] for a in resp.get_json()]


def test_announcement_requires_auth_and_lab(client, db_tables, lab, sa_headers):
    resp = client.get("/announcements")
    assert resp.status_code == 401

    resp = client.post(
        "/announcements",
        json={"lab_id": 999, "title": "X"},
        headers=sa_headers,
    )
    assert resp.status_code == 404

    resp = client.post(
        "/announcements",
        json={"lab_id": lab},
        headers=sa_headers,
    )
    assert resp.status_code == 422

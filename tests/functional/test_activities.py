# ── Public GET (no token required) ───────────────────────────────────────────


def test_list_activities_is_public(client, db_tables, lab):
    resp = client.get(f"/labs/{lab}/activities")
    assert resp.status_code == 200
    assert isinstance(resp.get_json(), list)


def test_get_activity_is_public(client, db_tables, lab, cs_headers):
    created = client.post(
        f"/labs/{lab}/activities", json={"title": "Public Activity"}, headers=cs_headers
    ).get_json()
    resp = client.get(f"/labs/{lab}/activities/{created['id']}")
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Public Activity"


def test_get_nonexistent_activity_returns_404(client, db_tables, lab):
    resp = client.get(f"/labs/{lab}/activities/9999")
    assert resp.status_code == 404


# ── Create ────────────────────────────────────────────────────────────────────


def test_researcher_can_create_activity(client, db_tables, lab, researcher, res_headers):
    resp = client.post(
        f"/labs/{lab}/activities",
        json={
            "title": "Researcher Activity",
            "venue": "Main Hall",
            "in_charge": [researcher],
        },
        headers=res_headers,
    )
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "Researcher Activity"
    assert len(data["in_charge"]) == 1
    assert data["in_charge"][0]["id"] == researcher


def test_engineer_can_create_activity(client, db_tables, lab, eng_headers):
    resp = client.post(
        f"/labs/{lab}/activities", json={"title": "Eng Activity"}, headers=eng_headers
    )
    assert resp.status_code == 403


def test_staff_cannot_create_activity(client, db_tables, lab, stf_headers):
    resp = client.post(
        f"/labs/{lab}/activities", json={"title": "Staff Activity"}, headers=stf_headers
    )
    assert resp.status_code == 403


def test_create_activity_without_token_returns_401(client, db_tables, lab):
    resp = client.post(f"/labs/{lab}/activities", json={"title": "Anon Activity"})
    assert resp.status_code == 401


# ── Update ────────────────────────────────────────────────────────────────────


def test_researcher_can_update_activity(client, db_tables, lab, res_headers):
    created = client.post(
        f"/labs/{lab}/activities", json={"title": "Draft"}, headers=res_headers
    ).get_json()
    resp = client.put(
        f"/labs/{lab}/activities/{created['id']}",
        json={"title": "Final"},
        headers=res_headers,
    )
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Final"


def test_researcher_can_update_activity_in_charge(
    client, db_tables, lab, researcher, manager, res_headers
):
    created = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Draft", "in_charge": [researcher]},
        headers=res_headers,
    ).get_json()
    resp = client.put(
        f"/labs/{lab}/activities/{created['id']}",
        json={"title": "Final", "in_charge": [manager]},
        headers=res_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["title"] == "Final"
    assert len(data["in_charge"]) == 1
    assert data["in_charge"][0]["id"] == manager


def test_create_and_update_activity_participants(
    client, db_tables, lab, researcher, manager, engineer, res_headers
):
    # Create with participants
    created = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Com participantes", "participants": [engineer]},
        headers=res_headers,
    ).get_json()
    assert created["status"] == "planned"
    assert [p["id"] for p in created["participants"]] == [engineer]

    # Update replaces participants
    resp = client.put(
        f"/labs/{lab}/activities/{created['id']}",
        json={"participants": [manager]},
        headers=res_headers,
    )
    assert resp.status_code == 200
    assert [p["id"] for p in resp.get_json()["participants"]] == [manager]

    # Invalid participant id
    resp = client.put(
        f"/labs/{lab}/activities/{created['id']}",
        json={"participants": [999999]},
        headers=res_headers,
    )
    assert resp.status_code == 422


# ── Delete ────────────────────────────────────────────────────────────────────


def test_manager_can_delete_activity(client, db_tables, lab, cs_headers):
    created = client.post(
        f"/labs/{lab}/activities", json={"title": "ToDelete"}, headers=cs_headers
    ).get_json()
    resp = client.delete(f"/labs/{lab}/activities/{created['id']}", headers=cs_headers)
    assert resp.status_code == 204


def test_researcher_cannot_delete_activity(client, db_tables, lab, res_headers, cs_headers):
    created = client.post(
        f"/labs/{lab}/activities", json={"title": "Protected"}, headers=cs_headers
    ).get_json()
    resp = client.delete(f"/labs/{lab}/activities/{created['id']}", headers=res_headers)
    assert resp.status_code == 403


# ── Participants ──────────────────────────────────────────────────────────────


def test_add_participant_to_activity(client, db_tables, lab, researcher, cs_headers):
    activity = client.post(
        f"/labs/{lab}/activities", json={"title": "Collab Activity"}, headers=cs_headers
    ).get_json()
    resp = client.post(
        f"/labs/{lab}/activities/{activity['id']}/participants",
        json={"member_id": researcher},
        headers=cs_headers,
    )
    assert resp.status_code == 200
    participant_ids = [p["id"] for p in resp.get_json()["participants"]]
    assert researcher in participant_ids


def test_add_duplicate_participant_returns_409(client, db_tables, lab, researcher, cs_headers):
    activity = client.post(
        f"/labs/{lab}/activities", json={"title": "Dup Participant"}, headers=cs_headers
    ).get_json()
    client.post(
        f"/labs/{lab}/activities/{activity['id']}/participants",
        json={"member_id": researcher},
        headers=cs_headers,
    )
    resp = client.post(
        f"/labs/{lab}/activities/{activity['id']}/participants",
        json={"member_id": researcher},
        headers=cs_headers,
    )
    assert resp.status_code == 409


def test_remove_participant_from_activity(client, db_tables, lab, researcher, cs_headers):
    activity = client.post(
        f"/labs/{lab}/activities",
        json={"title": "Remove Participant"},
        headers=cs_headers,
    ).get_json()
    client.post(
        f"/labs/{lab}/activities/{activity['id']}/participants",
        json={"member_id": researcher},
        headers=cs_headers,
    )
    resp = client.delete(
        f"/labs/{lab}/activities/{activity['id']}/participants/{researcher}",
        headers=cs_headers,
    )
    assert resp.status_code == 204

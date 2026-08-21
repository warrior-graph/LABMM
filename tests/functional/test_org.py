def _make(client, headers, email, cpf, first, last, lab, roles, reports_to=None):
    m = client.post(
        "/auth/register",
        json={
            "first_name": first,
            "last_name": last,
            "email": email,
            "password": "pass123",
            "cpf": cpf,
        },
        headers=headers,
    ).get_json()["member"]
    payload = {"member_id": m["id"], "roles": roles}
    if reports_to is not None:
        payload["reports_to_id"] = reports_to
    client.post(f"/labs/{lab}/members", json=payload, headers=headers)
    return m


def test_org_chart_deterministic_tree(client, db_tables, lab, super_admin, sa_headers):
    coord = _make(client, sa_headers, "coord@x.local", "10000000001", "Coord", "One", lab, ["lab_coordinator"])
    mgr1 = _make(client, sa_headers, "mgr1@x.local", "10000000002", "Mgr", "One", lab, ["engineering_manager"])
    mgr2 = _make(client, sa_headers, "mgr2@x.local", "10000000003", "Mgr", "Two", lab, ["engineering_manager"])
    tl = _make(client, sa_headers, "tl@x.local", "10000000004", "TL", "One", lab, ["tech_lead"], reports_to=mgr1["id"])
    eng = _make(client, sa_headers, "eng@x.local", "10000000005", "Eng", "One", lab, ["engineer"])

    resp = client.get(f"/labs/{lab}/org", headers=sa_headers)
    assert resp.status_code == 200
    data = resp.get_json()

    assert data["root_id"] == coord["id"]
    by_id = {m["member_id"]: m for m in data["memberships"]}

    assert by_id[coord["id"]]["resolved_reports_to_id"] is None
    assert by_id[mgr1["id"]]["resolved_reports_to_id"] == coord["id"]
    assert by_id[mgr2["id"]]["resolved_reports_to_id"] == coord["id"]
    # explicit reports_to wins (level 2 -> level 1)
    assert by_id[tl["id"]]["resolved_reports_to_id"] == mgr1["id"]
    # engineer (level 3) attaches to the nearest level above (tech_lead, level 2)
    assert by_id[eng["id"]]["resolved_reports_to_id"] == tl["id"]

    # single root: every non-root membership resolves to someone
    for m in data["memberships"]:
        if m["member_id"] == coord["id"]:
            continue
        assert m["resolved_reports_to_id"] is not None


def test_org_chart_requires_membership(client, db_tables, lab):
    # lab has no members -> 404? No: lab exists, returns empty. Auth required.
    resp = client.get(f"/labs/{lab}/org")
    assert resp.status_code == 401

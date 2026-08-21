def test_profile_enriched_fields(client, db_tables, lab, super_admin, sa_headers, engineer, eng_headers):
    resp = client.put(
        f"/members/{engineer}",
        json={"lattes_url": "http://lattes.cnpq.br/123", "orcid": "0000-0001-2345", "github_url": "https://github.com/x"},
        headers=eng_headers,
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["lattes_url"] == "http://lattes.cnpq.br/123"
    assert data["orcid"] == "0000-0001-2345"
    assert data["github_url"] == "https://github.com/x"


def test_leave_rejoin_and_history(client, db_tables, lab, super_admin, sa_headers, manager, mgr_headers):
    # history initially
    resp = client.get(f"/members/{manager}/history", headers=mgr_headers)
    assert resp.status_code == 200
    assert any(h["lab_id"] == lab for h in resp.get_json())

    # leave
    resp = client.post(f"/labs/{lab}/members/{manager}/leave", headers=mgr_headers)
    assert resp.status_code == 200
    assert resp.get_json()["left_at"] is not None

    # rejoin
    resp = client.post(f"/labs/{lab}/members/{manager}/rejoin", headers=mgr_headers)
    assert resp.status_code == 200
    assert resp.get_json()["left_at"] is None

    # history reflects the (rejoined) membership
    resp = client.get(f"/members/{manager}/history", headers=mgr_headers)
    assert any(h["lab_id"] == lab and h["left_at"] is None for h in resp.get_json())


def test_invite_flow(client, db_tables, lab, super_admin, sa_headers):
    # create invite (super-admin passes manager role)
    resp = client.post(f"/labs/{lab}/invites", json={"days": 7}, headers=sa_headers)
    assert resp.status_code == 201
    invite = resp.get_json()
    assert invite["token"]
    assert invite["url"].startswith("/register?invite=")

    # validate
    resp = client.get(f"/invites/{invite['token']}")
    assert resp.status_code == 200
    assert resp.get_json()["lab_id"] == lab

    # register with the invite -> auto-approved into the lab
    reg = client.post(
        "/auth/register",
        json={
            "first_name": "Convidada",
            "last_name": "Pessoa",
            "email": "convidada@x.local",
            "password": "pass123",
            "cpf": "12345678999",
            "invite_token": invite["token"],
        },
    )
    assert reg.status_code == 201
    member = reg.get_json()["member"]
    assert member["is_approved"] is True

    # the invited member can log in and is a member of the lab
    login = client.post("/auth/login", json={"email": "convidada@x.local", "password": "pass123"})
    assert login.status_code == 200
    resp = client.get(f"/labs/{lab}/members", headers=sa_headers)
    assert any(m["member_id"] == member["id"] for m in resp.get_json())

    # invite is single-use now
    resp = client.get(f"/invites/{invite['token']}")
    assert resp.status_code == 404

    # using the same token again fails
    resp = client.post(
        "/auth/register",
        json={
            "first_name": "Outra",
            "last_name": "Pessoa",
            "email": "outra@x.local",
            "password": "pass123",
            "cpf": "12345678988",
            "invite_token": invite["token"],
        },
    )
    assert resp.status_code == 404

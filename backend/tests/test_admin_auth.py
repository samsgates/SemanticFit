def test_admin_login(client):
    response = client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200
    session = client.get("/api/v1/admin/session").get_json()
    assert session["authenticated"] is True


def test_bad_admin_login(client):
    response = client.post("/api/v1/admin/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401

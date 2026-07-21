def test_login_sets_cookie_and_returns_user(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})

    assert response.status_code == 200
    body = response.json()
    assert response.cookies.get("apartment_auth")
    assert "HttpOnly" in response.headers["set-cookie"]
    assert body["user"]["role"] == "super_admin"
    assert "permissions:manage" in body["user"]["permissions"]


def test_login_rejects_bad_password(client):
    response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "INVALID_CREDENTIALS"


def test_protected_route_requires_session(client):
    response = client.get("/api/properties")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "AUTH_REQUIRED"


def test_me_uses_cookie_session(client, admin_token):
    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["role"] == "super_admin"


def test_logout_clears_cookie_session(client, admin_token):
    logout_response = client.post("/api/auth/logout")
    me_response = client.get("/api/auth/me")

    assert logout_response.status_code == 200
    assert client.cookies.get("apartment_auth") is None
    assert me_response.status_code == 401


def test_roles_requires_session(client):
    response = client.get("/api/auth/roles")

    assert response.status_code == 401


def test_roles_omits_permission_details(client, admin_token):
    response = client.get("/api/auth/roles")

    assert response.status_code == 200
    assert response.json()[0]["permissions"] == []


def test_login_rate_limits_repeated_failures(client):
    for _ in range(5):
        response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})
        assert response.status_code == 401

    response = client.post("/api/auth/login", json={"username": "admin", "password": "bad"})

    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "TOO_MANY_LOGIN_ATTEMPTS"


def test_login_rate_limits_username_spraying_from_same_client(client):
    for index in range(5):
        response = client.post("/api/auth/login", json={"username": f"missing-{index}", "password": "bad"})
        assert response.status_code == 401

    response = client.post("/api/auth/login", json={"username": "another-missing", "password": "bad"})

    assert response.status_code == 429


def test_login_rate_limit_ignores_spoofed_forwarded_for(client):
    for index in range(5):
        response = client.post(
            "/api/auth/login",
            headers={"X-Forwarded-For": f"203.0.113.{index}"},
            json={"username": f"spray-{index}", "password": "bad"},
        )
        assert response.status_code == 401

    response = client.post(
        "/api/auth/login",
        headers={"X-Forwarded-For": "203.0.113.99"},
        json={"username": "spray-final", "password": "bad"},
    )

    assert response.status_code == 429


def test_successful_login_only_clears_username_failure_bucket(client):
    for index in range(4):
        response = client.post("/api/auth/login", json={"username": f"missing-{index}", "password": "bad"})
        assert response.status_code == 401

    response = client.post("/api/auth/login", json={"username": "admin", "password": "admin123"})
    assert response.status_code == 200

    response = client.post("/api/auth/login", json={"username": "missing-final", "password": "bad"})
    assert response.status_code == 401

    response = client.post("/api/auth/login", json={"username": "missing-blocked", "password": "bad"})
    assert response.status_code == 429

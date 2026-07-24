"""End-to-end tests for the account API (register / login / invite / session).

Each test runs against a throwaway SQLite database created in a tmp_path, so the
real user_store + schema execute exactly as in production. The equivalent SQL and
hashing were also validated by direct execution.

Policy under test:
- The FIRST registrant becomes admin and needs no invite.
- Every later registration requires a valid, single-use invite code.
- Only admins can mint or list invites.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    # Point the shared connection at an isolated temp DB, then create tables.
    from app.db import connection as conn_mod

    monkeypatch.setattr(conn_mod, "_DB_PATH", tmp_path / "auth_test.db")
    conn_mod._connection = None  # force a fresh connection against the temp path

    from app.db import init_db
    from app.routers import auth

    init_db()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth")
    try:
        yield TestClient(app)
    finally:
        conn_mod.close_connection()
        conn_mod._connection = None


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_needs_setup_true_when_empty(client):
    assert client.get("/api/auth/needs-setup").json() == {"needs_setup": True}


def test_first_user_becomes_admin_without_invite(client):
    r = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    assert r.status_code == 200
    body = r.json()
    assert body["user"]["is_admin"] is True
    assert body["token"]
    # No longer needs setup once a user exists.
    assert client.get("/api/auth/needs-setup").json()["needs_setup"] is False


def test_second_registration_requires_invite(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    r = client.post("/api/auth/register", json={"username": "bob", "password": "pw123456"})
    assert r.status_code == 403


def test_duplicate_username_rejected(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})
    r = client.post("/api/auth/register", json={"username": "alice", "password": "other123"})
    assert r.status_code == 409


def test_invite_flow_and_single_use(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    headers = _auth(admin["token"])

    inv = client.post("/api/auth/invite", headers=headers)
    assert inv.status_code == 200
    code = inv.json()["code"]
    assert inv.json()["used"] is False

    # Admin can see the invite listed.
    listed = client.get("/api/auth/invites", headers=headers).json()
    assert any(i["code"] == code for i in listed)

    # Second user registers with the invite.
    r = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "pw123456", "invite_code": code},
    )
    assert r.status_code == 200
    assert r.json()["user"]["is_admin"] is False

    # The same invite cannot be reused.
    r2 = client.post(
        "/api/auth/register",
        json={"username": "carol", "password": "pw123456", "invite_code": code},
    )
    assert r2.status_code == 403


def test_non_admin_cannot_mint_invites(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    code = client.post("/api/auth/invite", headers=_auth(admin["token"])).json()["code"]
    bob = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "pw123456", "invite_code": code},
    ).json()

    assert client.post("/api/auth/invite", headers=_auth(bob["token"])).status_code == 403
    assert client.get("/api/auth/invites", headers=_auth(bob["token"])).status_code == 403


def test_login_success_and_failure(client):
    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})

    ok = client.post("/api/auth/login", json={"username": "alice", "password": "pw123456"})
    assert ok.status_code == 200 and ok.json()["token"]

    bad = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert bad.status_code == 401

    missing = client.post("/api/auth/login", json={"username": "ghost", "password": "pw123456"})
    assert missing.status_code == 401


def test_me_requires_token_and_logout_invalidates_session(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    token = admin["token"]

    assert client.get("/api/auth/me").status_code == 401  # no token
    assert client.get("/api/auth/me", headers=_auth(token)).json()["username"] == "alice"

    assert client.post("/api/auth/logout", headers=_auth(token)).json() == {"ok": True}
    # Session is gone after logout.
    assert client.get("/api/auth/me", headers=_auth(token)).status_code == 401

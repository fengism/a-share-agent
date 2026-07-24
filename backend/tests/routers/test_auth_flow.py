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
    from app.utils import login_throttle

    init_db()
    # All TestClient requests share client IP "testclient", so reset the
    # in-process login throttle to isolate tests from each other.
    login_throttle._reset_all()

    app = FastAPI()
    app.include_router(auth.router, prefix="/api/auth")
    try:
        yield TestClient(app)
    finally:
        login_throttle._reset_all()
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


def test_consumed_invite_leaves_no_orphan_account(client):
    """Regression: reusing a consumed invite must be rejected AND must not leave
    a usable orphan account behind (previously the user row was created before
    the invite was consumed, so a rejected registration could still log in)."""
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    code = client.post("/api/auth/invite", headers=_auth(admin["token"])).json()["code"]

    # First registration with the invite succeeds.
    r1 = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "pw123456", "invite_code": code},
    )
    assert r1.status_code == 200

    # Reusing the now-consumed invite is rejected ...
    r2 = client.post(
        "/api/auth/register",
        json={"username": "carol", "password": "pw123456", "invite_code": code},
    )
    assert r2.status_code == 403

    # ... and no orphan account was created for carol — she cannot log in.
    login = client.post("/api/auth/login", json={"username": "carol", "password": "pw123456"})
    assert login.status_code == 401


def test_create_account_atomic_rollback(client):
    """create_account rolls back the user insert when the invite is unavailable,
    and reports duplicate usernames without creating a second row."""
    from app.db import user_store
    from app.utils.auth import generate_invite_code

    admin = user_store.create_user("root", "pw123456", is_admin=True)
    code = generate_invite_code()
    user_store.create_invite(admin["id"], code)

    ok_status, ok_user = user_store.create_account("u1", "pw123456", is_admin=False, invite_code=code)
    assert ok_status == "ok" and ok_user is not None

    # Same code again → invite_taken, and no orphan "u2" survives the rollback.
    status, user = user_store.create_account("u2", "pw123456", is_admin=False, invite_code=code)
    assert status == "invite_taken" and user is None
    assert user_store.get_user_by_username("u2") is None

    # Duplicate username → duplicate status, still exactly one "u1".
    dup_status, dup_user = user_store.create_account("u1", "pw123456", is_admin=False, invite_code=None)
    assert dup_status == "duplicate" and dup_user is None


def test_create_invite_with_expiry_sets_expires_at(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    r = client.post("/api/auth/invite", headers=_auth(admin["token"]), json={"expires_in_days": 7})
    assert r.status_code == 200
    body = r.json()
    assert body["expires_at"] is not None
    assert body["used"] is False and body["expired"] is False


def test_expired_invite_is_rejected(client):
    from app.db import user_store
    from app.utils.auth import generate_invite_code, invite_expiry

    admin = user_store.create_user("root", "pw123456", is_admin=True)

    past = generate_invite_code()
    user_store.create_invite(admin["id"], past, expires_at=invite_expiry(-1))  # already expired
    assert user_store.invite_is_valid(past) is False
    status, user = user_store.create_account("bob", "pw123456", is_admin=False, invite_code=past)
    assert status == "invite_taken" and user is None

    future = generate_invite_code()
    user_store.create_invite(admin["id"], future, expires_at=invite_expiry(1))
    assert user_store.invite_is_valid(future) is True


def test_revoke_unused_invite(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    headers = _auth(admin["token"])
    code = client.post("/api/auth/invite", headers=headers).json()["code"]

    assert client.delete(f"/api/auth/invite/{code}", headers=headers).status_code == 200
    # A revoked invite is unusable and no longer listed.
    reg = client.post(
        "/api/auth/register",
        json={"username": "bob", "password": "pw123456", "invite_code": code},
    )
    assert reg.status_code == 403
    assert all(i["code"] != code for i in client.get("/api/auth/invites", headers=headers).json())


def test_cannot_revoke_used_invite(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    headers = _auth(admin["token"])
    code = client.post("/api/auth/invite", headers=headers).json()["code"]
    client.post("/api/auth/register", json={"username": "bob", "password": "pw123456", "invite_code": code})

    assert client.delete(f"/api/auth/invite/{code}", headers=headers).status_code == 409


def test_revoke_missing_invite_returns_404(client):
    admin = client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"}).json()
    assert client.delete("/api/auth/invite/does-not-exist", headers=_auth(admin["token"])).status_code == 404


def test_login_lockout_after_repeated_failures(client):
    from app.utils import login_throttle

    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})

    # The first (MAX_FAILURES - 1) wrong attempts are plain 401s ...
    for _ in range(login_throttle.MAX_FAILURES - 1):
        r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
        assert r.status_code == 401

    # ... the attempt hitting the threshold locks the account (429 + Retry-After) ...
    r = client.post("/api/auth/login", json={"username": "alice", "password": "wrong"})
    assert r.status_code == 429
    assert "retry-after" in {k.lower() for k in r.headers.keys()}

    # ... and even the correct password is refused while locked.
    r = client.post("/api/auth/login", json={"username": "alice", "password": "pw123456"})
    assert r.status_code == 429


def test_successful_login_resets_failure_counter(client):
    from app.utils import login_throttle

    client.post("/api/auth/register", json={"username": "alice", "password": "pw123456"})

    # Several failures short of the threshold, then a success clears the counter.
    for _ in range(login_throttle.MAX_FAILURES - 1):
        assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"username": "alice", "password": "pw123456"}).status_code == 200

    # Counter reset → a subsequent failure is a plain 401, not an immediate lock.
    assert client.post("/api/auth/login", json={"username": "alice", "password": "wrong"}).status_code == 401

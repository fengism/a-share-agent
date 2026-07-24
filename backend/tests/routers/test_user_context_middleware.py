"""Integration test for the per-user config chain end to end.

Exercises the real ASGI stack: UserContextMiddleware resolves the Bearer token
to a user, binds it into the request-scoped ContextVar, and get_effective_settings
overlays that user's private config. A tokenless or invalid request falls back to
the global instance settings.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    from app.db import connection as conn_mod

    monkeypatch.setattr(conn_mod, "_DB_PATH", tmp_path / "mw_test.db")
    conn_mod._connection = None

    from app.db import init_db, user_store
    from app.middleware import UserContextMiddleware
    from app.config import get_effective_settings

    init_db()
    alice = user_store.create_user("alice", "pw123456", is_admin=True)
    user_store.set_user_config(alice["id"], {"llm_api_key": "ALICE_KEY", "llm_model": "alice-model"})
    token = user_store.create_session(alice["id"])

    app = FastAPI()
    app.add_middleware(UserContextMiddleware)

    @app.get("/probe")
    async def probe():
        s = get_effective_settings()
        return {"llm_api_key": s.llm_api_key, "llm_model": s.llm_model}

    client = TestClient(app)
    try:
        yield client, token, get_effective_settings
    finally:
        conn_mod.close_connection()
        conn_mod._connection = None


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_bearer_token_overlays_user_private_config(ctx):
    client, token, _ = ctx
    body = client.get("/probe", headers=_auth(token)).json()
    assert body["llm_api_key"] == "ALICE_KEY"
    assert body["llm_model"] == "alice-model"


def test_no_token_falls_back_to_global(ctx):
    client, _, get_effective_settings = ctx
    body = client.get("/probe").json()
    base = get_effective_settings()  # called outside any request → global base
    assert body["llm_api_key"] == base.llm_api_key
    assert body["llm_api_key"] != "ALICE_KEY"


def test_invalid_token_falls_back_to_global(ctx):
    client, _, _ = ctx
    body = client.get("/probe", headers=_auth("not-a-real-token")).json()
    assert body["llm_api_key"] != "ALICE_KEY"


def test_middleware_slides_near_expiry_session(ctx):
    client, _, _ = ctx
    from app.db import connection as conn_mod
    from app.db import user_store
    from app.utils import auth as auth_mod

    alice_id = user_store.get_user_by_username("alice")["id"]
    conn = conn_mod.get_connection()
    conn.execute(
        "INSERT INTO auth_sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
        (auth_mod.hash_token("slide-token"), alice_id, auth_mod.session_expiry(1)),
    )
    conn.commit()

    # An authenticated request carrying the near-expiry token slides it forward.
    assert client.get("/probe", headers=_auth("slide-token")).status_code == 200

    new_exp = conn.execute(
        "SELECT expires_at FROM auth_sessions WHERE token_hash = ?",
        (auth_mod.hash_token("slide-token"),),
    ).fetchone()["expires_at"]
    assert new_exp > auth_mod.session_expiry(auth_mod.SESSION_RENEW_THRESHOLD_DAYS)

"""Per-user /api/config read/write tests (account-scoped).

Runs against a throwaway SQLite DB. Verifies login is required, private config
is isolated per user, masked secrets are not overwritten, and global fields are
admin-only.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def ctx(tmp_path, monkeypatch):
    from app.db import connection as conn_mod

    monkeypatch.setattr(conn_mod, "_DB_PATH", tmp_path / "config_test.db")
    conn_mod._connection = None

    from app.db import init_db, user_store
    from app.routers import config

    init_db()
    admin = user_store.create_user("admin", "pw123456", is_admin=True)
    member = user_store.create_user("member", "pw123456", is_admin=False)
    admin_token = user_store.create_session(admin["id"])
    member_token = user_store.create_session(member["id"])

    app = FastAPI()
    app.include_router(config.router, prefix="/api/config")
    client = TestClient(app)
    try:
        yield client, admin, member, admin_token, member_token
    finally:
        conn_mod.close_connection()
        conn_mod._connection = None


def _h(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_requires_login(ctx):
    client = ctx[0]
    assert client.get("/api/config").status_code == 401


def test_private_config_is_isolated_per_user(ctx):
    client, admin, member, at, mt = ctx

    r = client.put("/api/config", headers=_h(mt), json={"llm_model": "member-model"})
    assert r.status_code == 200
    assert r.json()["llm_model"] == "member-model"

    # Admin's effective view is unaffected by the member's private override.
    admin_view = client.get("/api/config", headers=_h(at)).json()
    assert admin_view["llm_model"] != "member-model"


def test_masked_secret_is_not_overwritten(ctx):
    client, admin, member, at, mt = ctx
    from app.db import user_store

    client.put("/api/config", headers=_h(mt), json={"llm_api_key": "REALKEY1234"})
    masked = client.get("/api/config", headers=_h(mt)).json()["llm_api_key"]
    assert masked.endswith("***")

    # Echoing the masked value back must not clobber the stored real key.
    client.put("/api/config", headers=_h(mt), json={"llm_api_key": masked})
    assert user_store.get_user_config(member["id"])["llm_api_key"] == "REALKEY1234"


def test_global_field_is_admin_only(ctx):
    client, admin, member, at, mt = ctx

    # Non-admin cannot change a global instance field.
    assert client.put("/api/config", headers=_h(mt), json={"http_trust_env": True}).status_code == 403

    # Admin can, and a partial patch of only the global field is accepted.
    r = client.put("/api/config", headers=_h(at), json={"http_trust_env": True})
    assert r.status_code == 200
    assert r.json()["http_trust_env"] is True

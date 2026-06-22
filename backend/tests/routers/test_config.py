from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.routers import config


def build_client() -> TestClient:
    """Create a TestClient with the config router mounted."""
    app = FastAPI()
    app.include_router(config.router, prefix="/api/config")
    return TestClient(app)


def test_put_config_accepts_partial_patch_without_required_unrelated_fields(monkeypatch):
    """PUT /api/config should allow patching a subset of fields."""
    captured_patch = {}

    class FakeSettings:
        llm_provider = "deepseek"
        llm_api_key = ""
        llm_base_url = "https://api.deepseek.com"
        llm_model = "deepseek-v4-flash"
        llm_temperature = 0.1
        admin_api_key = ""
        feishu_enabled = False
        feishu_app_id = ""
        feishu_app_secret = ""
        feishu_folder_token = ""
        feishu_wiki_space_id = ""
        feishu_wiki_daily_review_parent = ""
        feishu_wiki_analysis_parent = ""
        feishu_daily_review_folder = ""
        feishu_analysis_folder = ""
        feishu_default_receiver = ""
        notion_enabled = False
        notion_api_token = ""
        notion_parent_page_id = ""
        notion_database_id = ""
        iwencai_enabled = False
        iwencai_base_url = "https://openapi.iwencai.com"
        iwencai_api_key = ""
        http_trust_env = False
        twitter_feeds = ["qinbafrank"]
        eastmoney_cookie = ""
        baidu_cookie = ""
        ths_cookie = ""

    def fake_get_settings():
        return FakeSettings()

    def fake_update_settings(patch: dict):
        captured_patch.update(patch)
        settings = FakeSettings()
        for key, value in patch.items():
            setattr(settings, key, value)
        return settings

    monkeypatch.setattr(config, "get_settings", fake_get_settings)
    monkeypatch.setattr(config, "update_settings", fake_update_settings)

    response = build_client().put("/api/config", json={"twitter_feeds": ["wallstengine"]})

    assert response.status_code == 200
    assert captured_patch == {"twitter_feeds": ["wallstengine"]}
    assert response.json()["twitter_feeds"] == ["wallstengine"]

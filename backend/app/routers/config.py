from __future__ import annotations

import logging

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import PROVIDER_DEFAULTS, _mask_secret, get_settings, update_settings

logger = logging.getLogger(__name__)

router = APIRouter()


class ConfigResponse(BaseModel):
    """Purpose: 对外暴露的系统配置快照，敏感字段已掩码处理。"""

    llm_provider: str
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_temperature: float
    feishu_enabled: bool
    feishu_app_id: str
    feishu_app_secret: str
    feishu_folder_token: str
    feishu_wiki_space_id: str
    feishu_wiki_daily_review_parent: str
    feishu_wiki_analysis_parent: str
    feishu_daily_review_folder: str
    feishu_analysis_folder: str
    feishu_default_receiver: str
    notion_enabled: bool
    notion_parent_page_id: str
    notion_database_id: str
    iwencai_enabled: bool
    iwencai_base_url: str
    iwencai_api_key: str
    http_trust_env: bool
    provider_defaults: dict
    twitter_feeds: list[str]
    eastmoney_cookie: str
    baidu_acs_token: str


class ConfigUpdateRequest(BaseModel):
    """Purpose: 系统配置局部更新请求体，所有字段均为可选 patch。"""

    llm_provider: str | None = None
    llm_api_key: str | None = None
    llm_base_url: str | None = None
    llm_model: str | None = None
    llm_temperature: float | None = None
    feishu_enabled: bool | None = None
    feishu_app_id: str | None = None
    feishu_app_secret: str | None = None
    feishu_folder_token: str | None = None
    feishu_wiki_space_id: str | None = None
    feishu_wiki_daily_review_parent: str | None = None
    feishu_wiki_analysis_parent: str | None = None
    feishu_daily_review_folder: str | None = None
    feishu_analysis_folder: str | None = None
    feishu_default_receiver: str | None = None
    notion_enabled: bool | None = None
    notion_parent_page_id: str | None = None
    notion_database_id: str | None = None
    iwencai_enabled: bool | None = None
    iwencai_base_url: str | None = None
    iwencai_api_key: str | None = None
    http_trust_env: bool | None = None
    twitter_feeds: list[str] | None = None
    eastmoney_cookie: str | None = None
    baidu_acs_token: str | None = None


def _to_response(s) -> ConfigResponse:
    """将运行时 Settings 实例转换为对外的 ConfigResponse，敏感字段做掩码。

    Param:
        s: app.config.Settings 实例。
    Return:
        ConfigResponse: 用于 API 返回的配置快照。
    """
    return ConfigResponse(
        llm_provider=s.llm_provider,
        llm_api_key=_mask_secret(s.llm_api_key),
        llm_base_url=s.llm_base_url,
        llm_model=s.llm_model,
        llm_temperature=s.llm_temperature,
        feishu_enabled=s.feishu_enabled,
        feishu_app_id=s.feishu_app_id,
        feishu_app_secret=_mask_secret(s.feishu_app_secret),
        feishu_folder_token=s.feishu_folder_token,
        feishu_wiki_space_id=s.feishu_wiki_space_id,
        feishu_wiki_daily_review_parent=s.feishu_wiki_daily_review_parent,
        feishu_wiki_analysis_parent=s.feishu_wiki_analysis_parent,
        feishu_daily_review_folder=s.feishu_daily_review_folder,
        feishu_analysis_folder=s.feishu_analysis_folder,
        feishu_default_receiver=s.feishu_default_receiver,
        notion_enabled=s.notion_enabled,
        notion_parent_page_id=s.notion_parent_page_id,
        notion_database_id=s.notion_database_id,
        iwencai_enabled=s.iwencai_enabled,
        iwencai_base_url=s.iwencai_base_url,
        iwencai_api_key=_mask_secret(s.iwencai_api_key),
        http_trust_env=s.http_trust_env,
        provider_defaults=PROVIDER_DEFAULTS,
        twitter_feeds=s.twitter_feeds,
        eastmoney_cookie=_mask_secret(s.eastmoney_cookie),
        baidu_acs_token=_mask_secret(s.baidu_acs_token),
    )


@router.get("", response_model=ConfigResponse)
async def get_config():
    """读取当前生效的系统配置。

    Return:
        ConfigResponse: 当前 Settings 的脱敏快照。
    """
    return _to_response(get_settings())


@router.put("", response_model=ConfigResponse)
async def put_config(req: ConfigUpdateRequest):
    """部分更新系统配置；未提供的字段保持原值。

    Param:
        req: ConfigUpdateRequest 请求体，仅包含需要修改的字段。
    Return:
        ConfigResponse: 更新后生效的配置快照。
    """
    patch = req.model_dump(exclude_none=True)
    if not patch:
        return _to_response(get_settings())
    logger.info(f"Config update: {list(patch.keys())}")
    updated = update_settings(patch)
    return _to_response(updated)

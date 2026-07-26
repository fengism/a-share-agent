from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.config import (
    PRIVATE_USER_KEYS,
    PROVIDER_DEFAULTS,
    SECRET_KEYS,
    _mask_secret,
    effective_settings_for_user,
    update_settings,
)
from app.routers.auth import require_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


class ConfigResponse(BaseModel):
    """Purpose: 对外暴露的系统配置快照，敏感字段已掩码处理。

    返回的是“当前登录用户的生效配置”：全局实例基线叠加该用户的私密配置。
    is_admin 标识当前用户是否可修改全局项（twitter_feeds / http_trust_env / 数据源 Cookie 等）。
    """

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
    notion_api_token: str
    notion_parent_page_id: str
    notion_database_id: str
    iwencai_enabled: bool
    iwencai_base_url: str
    iwencai_api_key: str
    http_trust_env: bool
    provider_defaults: dict
    twitter_feeds: list[str]
    eastmoney_cookie: str
    baidu_cookie: str
    ths_cookie: str
    is_admin: bool


class ConfigUpdateRequest(BaseModel):
    """Purpose: 系统配置局部更新请求体，所有字段均为可选 patch。

    私密项（LLM / 飞书 / Notion / 问财）写入当前登录用户的私密配置；
    全局项（twitter_feeds / http_trust_env / 数据源 Cookie）仅管理员可改。
    """

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
    notion_api_token: str | None = None
    notion_parent_page_id: str | None = None
    notion_database_id: str | None = None
    iwencai_enabled: bool | None = None
    iwencai_base_url: str | None = None
    iwencai_api_key: str | None = None
    http_trust_env: bool | None = None
    twitter_feeds: list[str] | None = None
    eastmoney_cookie: str | None = None
    baidu_cookie: str | None = None
    ths_cookie: str | None = None


def _to_response(s, is_admin: bool = False) -> ConfigResponse:
    """将生效 Settings 转换为对外的 ConfigResponse，敏感字段做掩码。"""
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
        notion_api_token=_mask_secret(s.notion_api_token),
        notion_parent_page_id=s.notion_parent_page_id,
        notion_database_id=s.notion_database_id,
        iwencai_enabled=s.iwencai_enabled,
        iwencai_base_url=s.iwencai_base_url,
        iwencai_api_key=_mask_secret(s.iwencai_api_key),
        http_trust_env=s.http_trust_env,
        provider_defaults=PROVIDER_DEFAULTS,
        twitter_feeds=s.twitter_feeds,
        eastmoney_cookie=_mask_secret(s.eastmoney_cookie),
        baidu_cookie=_mask_secret(s.baidu_cookie),
        ths_cookie=_mask_secret(s.ths_cookie),
        is_admin=is_admin,
    )


@router.get("", response_model=ConfigResponse)
async def get_config(user: dict = Depends(require_active_user)):
    """读取当前登录用户的生效配置（全局基线叠加其私密配置），敏感字段脱敏。"""
    settings = effective_settings_for_user(user["id"])
    return _to_response(settings, is_admin=bool(user["is_admin"]))


@router.put("", response_model=ConfigResponse)
async def put_config(req: ConfigUpdateRequest, user: dict = Depends(require_active_user)):
    """部分更新配置。

    - 私密项写入当前用户的私密配置（掩码回传的密钥视为未修改，跳过）。
    - 全局项仅管理员可修改；非管理员提交全局项将被拒绝。
    """
    patch = req.model_dump(exclude_none=True)
    if not patch:
        return _to_response(effective_settings_for_user(user["id"]), is_admin=bool(user["is_admin"]))

    private_patch = {k: v for k, v in patch.items() if k in PRIVATE_USER_KEYS}
    global_patch = {k: v for k, v in patch.items() if k not in PRIVATE_USER_KEYS}

    if global_patch and not user["is_admin"]:
        raise HTTPException(
            status_code=403,
            detail="仅管理员可修改全局配置项: " + ", ".join(sorted(global_patch)),
        )

    # 写入每用户私密配置：掩码未变更的密钥（以 *** 结尾）跳过，避免用掩码覆盖真实值。
    to_store = {
        k: v
        for k, v in private_patch.items()
        if not (k in SECRET_KEYS and isinstance(v, str) and "***" in v)
    }
    if to_store:
        from app.db import user_store

        user_store.set_user_config(user["id"], to_store)

    if global_patch:
        update_settings(global_patch)

    logger.info(
        "Config update by user=%s private=%s global=%s",
        user["id"], list(private_patch.keys()), list(global_patch.keys()),
    )
    return _to_response(effective_settings_for_user(user["id"]), is_admin=bool(user["is_admin"]))

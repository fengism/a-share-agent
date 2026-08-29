from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime

from app.configuration import get_effective_settings
from app.domain.content import ContentBlock
from app.infrastructure.integrations.feishu.adapter import to_feishu_card, to_feishu_doc_blocks
from app.infrastructure.integrations.feishu.client import feishu_client
from app.infrastructure.integrations.feishu.errors import FeishuConfigError
from app.infrastructure.integrations.notion.adapter import to_notion_blocks
from app.infrastructure.integrations.notion.client import notion_client
from app.infrastructure.integrations.notion.errors import NotionConfigError
from app.modules.analysis.public import get_analysis_by_date, get_latest_analysis
from app.modules.daily_review.public import load_daily_review
from app.modules.industry_chain.public import load_industry_chain
from app.modules.push.content import build_content
from app.modules.push.schemas import PushRequest, PushResponse

logger = logging.getLogger(__name__)
_FEISHU_RECEIVER_PATTERN = re.compile(r"^(?:oc_|ou_)[A-Za-z0-9_-]+$")


@dataclass(frozen=True)
class ResolvedPushContent:
    """已解析好的推送内容。"""

    title: str
    content: list[ContentBlock]
    receiver: str = ""


class PushIntegrationNotConfiguredError(RuntimeError):
    """推送目标缺少必要配置。"""


def _resolve_feishu_receiver(request: PushRequest) -> str:
    """解析飞书接收人，优先请求参数，其次系统默认配置。"""
    receiver = request.feishu_receiver.strip()
    if not receiver:
        receiver = get_effective_settings().feishu_default_receiver.strip()
    if receiver and not _FEISHU_RECEIVER_PATTERN.fullmatch(receiver):
        raise ValueError("飞书接收人 ID 必须以 oc_ 或 ou_ 开头")
    return receiver


def _resolve_content(request: PushRequest, user_id: int) -> ResolvedPushContent:
    """将推送请求解析为标题、内容和接收人。"""
    receiver = _resolve_feishu_receiver(request) if request.target == "feishu" else ""
    if request.target == "feishu" and not receiver:
        raise ValueError("feishu_receiver is required for feishu push")

    if request.type == "chat":
        if not request.chat_content.strip():
            raise ValueError("chat_content 不能为空")
        title = request.chat_title or f"AI 对话 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        return ResolvedPushContent(
            title=title,
            content=build_content("chat", request.chat_content),
            receiver=receiver,
        )

    if request.type == "daily_review":
        data = load_daily_review(request.date, user_id)
        if data is None:
            raise LookupError("暂无复盘记录，请先生成")
        return ResolvedPushContent(
            title=f"每日复盘 - {data.date}",
            content=build_content("daily_review", data),
            receiver=receiver,
        )

    if request.type == "analysis":
        cache_ttl = get_effective_settings().cache_ttl_analysis
        data = (
            get_analysis_by_date(request.code, request.date, user_id, cache_ttl=cache_ttl)
            if request.date
            else get_latest_analysis(request.code, user_id, cache_ttl=cache_ttl)
        )
        if data is None:
            raise LookupError("暂无分析结果，请先生成")
        return ResolvedPushContent(
            title=f"个股研究 - {data.stock_code} - {data.stock_name} - {data.analysis_date}",
            content=build_content("analysis", data),
            receiver=receiver,
        )

    if request.type == "industry_chain":
        if not request.industry_name.strip() or not request.archive_id.strip():
            raise LookupError("暂无产业链存档，请先生成")
        data = load_industry_chain(request.industry_name, request.archive_id, user_id)
        if data is None:
            raise LookupError("暂无产业链存档，请先生成")
        return ResolvedPushContent(
            title=f"产业链分析 - {request.industry_name} - {request.archive_id}",
            content=build_content("industry_chain", data),
            receiver=receiver,
        )

    raise ValueError(f"unsupported push type: {request.type}")


def _push_to_notion(resolved: ResolvedPushContent) -> PushResponse:
    """推送内容到 Notion。"""
    blocks = to_notion_blocks(resolved.content)
    result = notion_client.create_page(resolved.title, blocks)
    return PushResponse(success=True, target="notion", url=result.url, title=result.title)


def _push_to_feishu(request: PushRequest, resolved: ResolvedPushContent) -> PushResponse:
    """推送内容到飞书。"""
    if request.type == "chat":
        card = to_feishu_card(request.type, resolved.title, resolved.content, "")
        feishu_client.send_card(resolved.receiver, card)
        return PushResponse(
            success=True,
            target="feishu",
            url="",
            title=resolved.title,
            message=f"已推送到 {resolved.receiver}",
        )

    settings = get_effective_settings()
    folder_map = {
        "daily_review": settings.feishu_daily_review_folder,
        "analysis": settings.feishu_analysis_folder,
        "industry_chain": settings.feishu_analysis_folder,
    }
    wiki_parent_map = {
        "daily_review": settings.feishu_wiki_daily_review_parent,
        "analysis": settings.feishu_wiki_analysis_parent,
    }
    result = feishu_client.create_doc(
        resolved.title,
        to_feishu_doc_blocks(resolved.content),
        folder_token=folder_map.get(request.type, ""),
        wiki_space_id=settings.feishu_wiki_space_id.strip(),
        wiki_parent_node_token=wiki_parent_map.get(request.type, "").strip(),
    )
    doc_url = result["url"]
    node_token = result["node_token"]
    try:
        if node_token:
            feishu_client.grant_doc_edit_permission(
                node_token,
                resolved.receiver,
                doc_type="wiki",
            )
        else:
            feishu_client.grant_doc_edit_permission(
                doc_url.rsplit("/", 1)[-1],
                resolved.receiver,
            )
    except Exception:
        logger.exception(
            "飞书文档已创建但权限授予失败: title=%s receiver=%s url=%s",
            resolved.title,
            resolved.receiver,
            doc_url,
        )
        return PushResponse(
            success=False,
            target="feishu",
            url=doc_url,
            title=resolved.title,
            message="文档已创建，但接收人权限授予失败",
        )
    try:
        feishu_client.send_card(
            resolved.receiver,
            to_feishu_card(request.type, resolved.title, resolved.content, doc_url),
        )
    except Exception:
        logger.exception(
            "飞书文档已创建但消息通知失败: title=%s receiver=%s url=%s",
            resolved.title,
            resolved.receiver,
            doc_url,
        )
        return PushResponse(
            success=False,
            target="feishu",
            url=doc_url,
            title=resolved.title,
            message="文档已创建，但消息通知失败",
        )
    return PushResponse(
        success=True,
        target="feishu",
        url=doc_url,
        title=resolved.title,
        message=f"已推送到 {resolved.receiver}",
    )


def execute_push(request: PushRequest, user_id: int) -> PushResponse:
    """执行推送请求，返回统一响应模型。"""
    try:
        resolved = _resolve_content(request, user_id)
        if request.target == "notion":
            return _push_to_notion(resolved)
        if request.target == "feishu":
            return _push_to_feishu(request, resolved)
        raise ValueError(f"unsupported push target: {request.target}")
    except (NotionConfigError, FeishuConfigError) as error:
        raise PushIntegrationNotConfiguredError(str(error)) from error

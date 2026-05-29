import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.models.push import PushRequest, PushResponse
from app.adapters.content import build_content
from app.adapters.notion import NotionConfigError, create_page, to_notion_blocks
from app.adapters.feishu import FeishuConfigError, create_doc, grant_doc_edit_permission, send_card, to_feishu_doc_blocks, to_feishu_card
from app.config import get_settings
from app.services.daily_review.storage import load_daily_review
from app.utils.cache import cache

logger = logging.getLogger(__name__)
router = APIRouter()


def _load_data(push_type: str, request: PushRequest):
    if push_type == "daily_review":
        return load_daily_review(request.date)
    if push_type == "analysis":
        today = datetime.now().strftime("%Y%m%d")
        cache_key = f"analysis:{request.code}:{today}"
        return cache.get(cache_key)
    return None


def _extract_title(push_type: str, request: PushRequest) -> str:
    if push_type == "daily_review":
        data = load_daily_review(request.date)
        return f"每日复盘 - {data.date}"
    if push_type == "analysis":
        today = datetime.now().strftime("%Y%m%d")
        cache_key = f"analysis:{request.code}:{today}"
        data = cache.get(cache_key)
        return f"股票分析 - {data.stock_code} - {data.stock_name} - {data.analysis_date}"
    if push_type == "chat":
        return request.chat_title or f"AI 对话 - {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    return "推送"


@router.post("", response_model=PushResponse)
async def push_content(request: PushRequest):
    if request.target == "feishu":
        if not request.feishu_receiver.strip():
            settings = get_settings()
            request.feishu_receiver = settings.feishu_default_receiver
        if not request.feishu_receiver.strip():
            raise HTTPException(status_code=400, detail="feishu_receiver is required for feishu push")

    if request.type == "chat":
        if not request.chat_content.strip():
            raise HTTPException(status_code=400, detail="chat_content 不能为空")
        content = build_content("chat", request.chat_content)
        title = _extract_title("chat", request)
    else:
        data = _load_data(request.type, request)
        if data is None:
            label = "复盘记录" if request.type == "daily_review" else "分析结果"
            raise HTTPException(status_code=404, detail=f"暂无{label}，请先生成")
        content = build_content(request.type, data)
        title = _extract_title(request.type, request)

    try:
        if request.target == "notion":
            blocks = to_notion_blocks(content)
            result = create_page(title, blocks)
            return PushResponse(success=True, target="notion", url=result.url, title=result.title)

        if request.target == "feishu":
            settings = get_settings()
            if request.type == "chat":
                card = to_feishu_card(request.type, title, content, "")
                send_card(request.feishu_receiver.strip(), card)
                return PushResponse(success=True, target="feishu", url="", title=title, message=f"已推送到 {request.feishu_receiver}")
            folder_map = {
                "daily_review": settings.feishu_daily_review_folder,
                "analysis": settings.feishu_analysis_folder,
            }
            wiki_parent_map = {
                "daily_review": settings.feishu_wiki_daily_review_parent,
                "analysis": settings.feishu_wiki_analysis_parent,
            }
            folder_token = folder_map.get(request.type, "")
            wiki_space_id = settings.feishu_wiki_space_id.strip()
            wiki_parent_node_token = wiki_parent_map.get(request.type, "").strip()
            doc_blocks = to_feishu_doc_blocks(content)
            result = create_doc(title, doc_blocks, folder_token=folder_token, wiki_space_id=wiki_space_id, wiki_parent_node_token=wiki_parent_node_token)
            doc_url = result["url"]
            node_token = result["node_token"]
            if node_token:
                grant_doc_edit_permission(node_token, request.feishu_receiver.strip(), doc_type="wiki")
            else:
                doc_id = doc_url.rsplit("/", 1)[-1]
                grant_doc_edit_permission(doc_id, request.feishu_receiver.strip())
            card = to_feishu_card(request.type, title, content, doc_url)
            send_card(request.feishu_receiver.strip(), card)
            return PushResponse(success=True, target="feishu", url=doc_url, title=title, message=f"已推送到 {request.feishu_receiver}")

    except (NotionConfigError, FeishuConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("推送失败: target=%s, type=%s, error=%s", request.target, request.type, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"推送失败: {exc}")

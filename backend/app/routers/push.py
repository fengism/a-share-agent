import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.models.push import PushRequest, PushResponse
from app.adapters.notion import NotionConfigError
from app.adapters.feishu import FeishuConfigError
from app.services.push import execute_push

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("", response_model=PushResponse)
async def push_content(request: PushRequest):
    """将分析结果、复盘或聊天内容推送到 Notion 或飞书。

    Param:
        request: PushRequest 请求体，包含 target、type、receiver 及内容字段。
    Return:
        PushResponse: 推送结果，含目标、文档 URL、标题和提示信息。
    """
    try:
        return await asyncio.to_thread(execute_push, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (NotionConfigError, FeishuConfigError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("推送失败: target=%s, type=%s, error=%s", request.target, request.type, exc, exc_info=True)
        raise HTTPException(status_code=502, detail=f"推送失败: {exc}")

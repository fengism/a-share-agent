from __future__ import annotations

import json
import logging
import time

import requests

from app.config import get_settings

logger = logging.getLogger(__name__)

_TOKEN_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
_DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
_PERMISSION_URL = "https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members"
_DRIVE_FILE_URL = "https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
_WIKI_NODE_URL = "https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"

_cached_token: str = ""
_token_expires_at: float = 0.0


class FeishuConfigError(RuntimeError):
    pass


def _validate_settings():
    settings = get_settings()
    if not settings.feishu_enabled:
        raise FeishuConfigError("FEISHU_ENABLED must be true to push to Feishu")
    if not settings.feishu_app_id.strip() or not settings.feishu_app_secret.strip():
        raise FeishuConfigError("FEISHU_APP_ID and FEISHU_APP_SECRET are required to push to Feishu")
    return settings


def get_tenant_token() -> str:
    global _cached_token, _token_expires_at
    if _cached_token and time.time() < _token_expires_at:
        return _cached_token

    _validate_settings()
    settings = get_settings()
    response = requests.post(
        _TOKEN_URL,
        json={"app_id": settings.feishu_app_id.strip(), "app_secret": settings.feishu_app_secret.strip()},
        timeout=10,
    )
    if response.status_code >= 400:
        raise RuntimeError(f"飞书认证失败: {response.text[:300]}")
    data = response.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"飞书认证失败: {data.get('msg', 'unknown error')}")
    _cached_token = data["tenant_access_token"]
    _token_expires_at = time.time() + data.get("expire", 7200) - 300
    return _cached_token


def _auth_headers() -> dict:
    return {"Authorization": f"Bearer {get_tenant_token()}", "Content-Type": "application/json"}


def create_doc(
    title: str,
    blocks: list[dict],
    folder_token: str = "",
    wiki_space_id: str = "",
    wiki_parent_node_token: str = "",
) -> dict:
    settings = _validate_settings()
    wiki_space_id = wiki_space_id.strip() or settings.feishu_wiki_space_id.strip()
    folder_token = folder_token.strip() or settings.feishu_folder_token.strip()

    if wiki_space_id:
        return _create_wiki_doc(title, blocks, wiki_space_id, wiki_parent_node_token)
    if folder_token:
        return _create_drive_doc(title, blocks, folder_token)
    raise FeishuConfigError("FEISHU_FOLDER_TOKEN or FEISHU_WIKI_SPACE_ID is required to create Feishu docs")


def _create_drive_doc(title: str, blocks: list[dict], folder_token: str = "") -> dict:
    doc_id = _create_docx(title, folder_token=folder_token)
    _write_blocks(doc_id, blocks)
    return {"url": f"https://feishu.cn/docx/{doc_id}", "node_token": ""}


def _create_wiki_doc(title: str, blocks: list[dict], wiki_space_id: str, wiki_parent_node_token: str = "") -> dict:
    source_doc_id = _create_docx(title)
    node_token, wiki_doc_id = create_wiki_node(
        wiki_space_id,
        source_doc_id,
        title=title,
        parent_node_token=wiki_parent_node_token,
    )
    logger.info(f"飞书Wiki挂载成功: node_token={node_token}, obj_token={wiki_doc_id}, source_doc_id={source_doc_id}")
    time.sleep(1)
    _write_blocks(wiki_doc_id, blocks)
    if wiki_doc_id != source_doc_id:
        _delete_drive_file(source_doc_id, file_type="docx")
    return {"url": f"https://feishu.cn/wiki/{node_token}", "node_token": node_token}


def _create_docx(title: str, folder_token: str = "") -> str:
    body: dict = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token
    data = _post_json(_DOC_URL, body, "飞书文档创建失败", timeout=20)
    doc_id = data["data"]["document"]["document_id"]
    logger.info(f"飞书文档创建成功: doc_id={doc_id}, title={title}")
    return doc_id


def _post_json(url: str, body: dict, error_prefix: str, *, timeout: int = 10, params: dict | None = None) -> dict:
    response = requests.post(url, headers=_auth_headers(), params=params, json=body, timeout=timeout)
    return _parse_response(response, error_prefix)


def _parse_response(response, error_prefix: str) -> dict:
    if response.status_code >= 400:
        raise RuntimeError(f"{error_prefix}: {response.text[:300]}")
    data = response.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"{error_prefix}: {data.get('msg', 'unknown error')}")
    return data


def _delete_drive_file(file_token: str, file_type: str = "docx") -> None:
    response = requests.delete(
        _DRIVE_FILE_URL.format(file_token=file_token),
        headers=_auth_headers(),
        params={"type": file_type},
        timeout=10,
    )
    try:
        _parse_response(response, "飞书源文档删除失败")
    except RuntimeError as exc:
        logger.warning(str(exc))


def _write_blocks(doc_id: str, blocks: list[dict]) -> None:
    """通过 Docx block children API 写入文档内容"""
    if not blocks:
        logger.warning(f"飞书文档写入跳过: blocks为空, doc_id={doc_id}")
        return
    children_url = f"{_DOC_URL}/{doc_id}/blocks/{doc_id}/children"
    logger.info(f"飞书文档写入: doc_id={doc_id}, blocks_count={len(blocks)}, first_block={blocks[0] if blocks else None}")
    resp = requests.post(
        children_url,
        headers=_auth_headers(),
        json={"children": blocks, "index": -1, "document_revision_id": -1},
        timeout=20,
    )
    try:
        _parse_response(resp, "飞书文档内容写入失败(文档已创建)")
    except RuntimeError as exc:
        logger.warning(str(exc))


def create_wiki_node(
    space_id: str,
    obj_token: str,
    obj_type: str = "docx",
    title: str = "",
    parent_node_token: str = "",
) -> tuple[str, str]:
    """将文档挂载为知识库节点，返回 (node_token, wiki_obj_token)"""
    body: dict = {"obj_type": obj_type, "obj_token": obj_token, "node_type": "origin"}
    if title.strip():
        body["title"] = title.strip()
    if parent_node_token.strip():
        body["parent_node_token"] = parent_node_token.strip()
    url = _WIKI_NODE_URL.format(space_id=space_id)
    data = _post_json(url, body, "飞书知识库节点创建失败", timeout=20)
    node = data["data"]["node"]
    return node["node_token"], node["obj_token"]


def grant_doc_edit_permission(doc_id: str, receiver: str, doc_type: str = "docx") -> None:
    """给接收人授予文档编辑权限。Wiki 文档传 doc_type="wiki" """
    member_type = "openid" if not receiver.startswith("oc_") else "chat_id"
    url = _PERMISSION_URL.format(token=doc_id)
    response = requests.post(
        url,
        headers=_auth_headers(),
        params={"type": doc_type, "need_notification": "false"},
        json={
            "member_type": member_type,
            "member_id": receiver,
            "perm": "full_access",
        },
        timeout=10,
    )
    try:
        _parse_response(response, "飞书文档权限授予失败")
    except RuntimeError as exc:
        logger.warning(str(exc))


def send_card(receiver: str, card: dict) -> None:
    _validate_settings()
    receive_id_type = "chat_id" if receiver.startswith("oc_") else "open_id"
    _post_json(
        _MESSAGE_URL,
        {
            "receive_id": receiver,
            "msg_type": "interactive",
            "content": json.dumps(card),
        },
        "飞书消息发送失败",
        params={"receive_id_type": receive_id_type},
    )

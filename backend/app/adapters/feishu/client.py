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
    """Purpose: 飞书推送相关配置缺失或非法时抛出的异常。"""


def _validate_settings():
    """校验飞书相关配置项是否启用并已填写。

    Param:
        无
    Return:
        校验通过的 Settings 实例
    """
    settings = get_settings()
    if not settings.feishu_enabled:
        raise FeishuConfigError("FEISHU_ENABLED must be true to push to Feishu")
    if not settings.feishu_app_id.strip() or not settings.feishu_app_secret.strip():
        raise FeishuConfigError("FEISHU_APP_ID and FEISHU_APP_SECRET are required to push to Feishu")
    return settings


def get_tenant_token() -> str:
    """获取飞书 tenant_access_token，自动缓存并在过期前刷新。

    Param:
        无
    Return:
        飞书 tenant_access_token 字符串
    """
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
    """构造飞书 API 请求所需的认证头。

    Param:
        无
    Return:
        包含 Authorization 和 Content-Type 的请求头 dict
    """
    return {"Authorization": f"Bearer {get_tenant_token()}", "Content-Type": "application/json"}


def create_doc(
    title: str,
    blocks: list[dict],
    folder_token: str = "",
    wiki_space_id: str = "",
    wiki_parent_node_token: str = "",
) -> dict:
    """在飞书云空间或知识库中创建文档并写入内容。

    Param:
        title: 文档标题
        blocks: 飞书文档块 dict 列表
        folder_token: 云空间目录 token，为空时使用配置默认值
        wiki_space_id: 知识库空间 ID，为空时使用配置默认值；非空时优先在知识库中创建
        wiki_parent_node_token: 知识库父节点 token
    Return:
        包含 url 和 node_token 的 dict
    """
    settings = _validate_settings()
    wiki_space_id = wiki_space_id.strip() or settings.feishu_wiki_space_id.strip()
    folder_token = folder_token.strip() or settings.feishu_folder_token.strip()

    if wiki_space_id:
        return _create_wiki_doc(title, blocks, wiki_space_id, wiki_parent_node_token)
    if folder_token:
        return _create_drive_doc(title, blocks, folder_token)
    raise FeishuConfigError("FEISHU_FOLDER_TOKEN or FEISHU_WIKI_SPACE_ID is required to create Feishu docs")


def _create_drive_doc(title: str, blocks: list[dict], folder_token: str = "") -> dict:
    """在飞书云空间目录下创建文档并写入内容。

    Param:
        title: 文档标题
        blocks: 飞书文档块 dict 列表
        folder_token: 云空间目录 token
    Return:
        包含 url 和 node_token 的 dict
    """
    doc_id = _create_docx(title, folder_token=folder_token)
    _write_blocks(doc_id, blocks)
    return {"url": f"https://feishu.cn/docx/{doc_id}", "node_token": ""}


def _create_wiki_doc(title: str, blocks: list[dict], wiki_space_id: str, wiki_parent_node_token: str = "") -> dict:
    """在飞书知识库中创建节点并写入文档内容。

    Param:
        title: 文档标题
        blocks: 飞书文档块 dict 列表
        wiki_space_id: 知识库空间 ID
        wiki_parent_node_token: 父节点 token
    Return:
        包含 url 和 node_token 的 dict
    """
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
    """调用飞书 Docx API 创建一个空文档。

    Param:
        title: 文档标题
        folder_token: 云空间目录 token，可选
    Return:
        新创建文档的 document_id
    """
    body: dict = {"title": title}
    if folder_token:
        body["folder_token"] = folder_token
    data = _post_json(_DOC_URL, body, "飞书文档创建失败", timeout=20)
    doc_id = data["data"]["document"]["document_id"]
    logger.info(f"飞书文档创建成功: doc_id={doc_id}, title={title}")
    return doc_id


def _post_json(url: str, body: dict, error_prefix: str, *, timeout: int = 10, params: dict | None = None) -> dict:
    """发送带认证头的 POST JSON 请求并解析响应。

    Param:
        url: 请求 URL
        body: 请求体 dict
        error_prefix: 错误信息前缀
        timeout: 超时秒数
        params: 查询参数字典
    Return:
        解析后的响应体 dict
    """
    response = requests.post(url, headers=_auth_headers(), params=params, json=body, timeout=timeout)
    return _parse_response(response, error_prefix)


def _parse_response(response, error_prefix: str) -> dict:
    """解析飞书 API 响应，校验 HTTP 状态码和业务 code。

    Param:
        response: requests.Response 对象
        error_prefix: 错误信息前缀
    Return:
        解析后的响应体 dict
    """
    if response.status_code >= 400:
        raise RuntimeError(f"{error_prefix}: {response.text[:300]}")
    data = response.json()
    if data.get("code", -1) != 0:
        raise RuntimeError(f"{error_prefix}: {data.get('msg', 'unknown error')}")
    return data


def _delete_drive_file(file_token: str, file_type: str = "docx") -> None:
    """删除飞书云空间中的文件，失败时仅记录警告日志。

    Param:
        file_token: 文件 token
        file_type: 文件类型，默认为 docx
    Return:
        无
    """
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
    """通过 Docx block children API 写入文档内容，超过 50 个块时分批写入。

    飞书 Docx 单次请求 children 字段上限为 50，业内接口验报错 code=99992402。
    分批时按顺序 append，每批使用 index=-1（末尾追加）。

    Param:
        doc_id: 飞书文档 ID
        blocks: 飞书文档块 dict 列表
    Return:
        无；任一批次失败时记录警告但继续后续批次
    """
    if not blocks:
        logger.warning(f"飞书文档写入跳过: blocks为空, doc_id={doc_id}")
        return
    chunk_size = 50
    children_url = f"{_DOC_URL}/{doc_id}/blocks/{doc_id}/children"
    logger.info(f"飞书文档写入: doc_id={doc_id}, blocks_count={len(blocks)}, first_block={blocks[0] if blocks else None}")
    for start in range(0, len(blocks), chunk_size):
        chunk = blocks[start:start + chunk_size]
        resp = requests.post(
            children_url,
            headers=_auth_headers(),
            json={"children": chunk, "index": -1, "document_revision_id": -1},
            timeout=20,
        )
        try:
            _parse_response(resp, f"飞书文档内容写入失败(批次 {start // chunk_size + 1}, 文档已创建)")
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
    """向指定用户或群发送飞书交互式卡片消息。

    Param:
        receiver: 接收者 open_id 或 chat_id
        card: 飞书交互式卡片 dict
    Return:
        无
    """
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

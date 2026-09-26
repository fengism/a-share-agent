"""飞书文档、知识库与权限操作。"""

import logging
from collections.abc import Callable

from app.infrastructure.integrations.feishu.errors import FeishuConfigError
from app.infrastructure.integrations.feishu.transport import FeishuTransport

logger = logging.getLogger(__name__)

DOC_URL = "https://open.feishu.cn/open-apis/docx/v1/documents"
PERMISSION_URL = "https://open.feishu.cn/open-apis/drive/v1/permissions/{token}/members"
DRIVE_FILE_URL = "https://open.feishu.cn/open-apis/drive/v1/files/{file_token}"
WIKI_NODE_URL = "https://open.feishu.cn/open-apis/wiki/v2/spaces/{space_id}/nodes"


class FeishuDocumentClient:
    def __init__(
        self,
        transport: FeishuTransport,
        *,
        sleep: Callable[[float], None],
    ) -> None:
        self._transport = transport
        self._sleep = sleep

    def create_doc(
        self,
        title: str,
        blocks: list[dict],
        folder_token: str = "",
        wiki_space_id: str = "",
        wiki_parent_node_token: str = "",
    ) -> dict:
        settings = self._transport.auth.validate_settings()
        resolved_wiki_space = wiki_space_id.strip() or settings.feishu_wiki_space_id.strip()
        resolved_folder = folder_token.strip() or settings.feishu_folder_token.strip()
        if resolved_wiki_space:
            return self._create_wiki_doc(
                title,
                blocks,
                resolved_wiki_space,
                wiki_parent_node_token,
            )
        if resolved_folder:
            return self._create_drive_doc(title, blocks, resolved_folder)
        raise FeishuConfigError(
            "FEISHU_FOLDER_TOKEN or FEISHU_WIKI_SPACE_ID is required to create Feishu docs"
        )

    def _create_drive_doc(
        self,
        title: str,
        blocks: list[dict],
        folder_token: str,
    ) -> dict:
        doc_id = self._create_docx(title, folder_token=folder_token)
        self._write_blocks(doc_id, blocks)
        return {"url": f"https://feishu.cn/docx/{doc_id}", "node_token": ""}

    def _create_wiki_doc(
        self,
        title: str,
        blocks: list[dict],
        wiki_space_id: str,
        wiki_parent_node_token: str = "",
    ) -> dict:
        source_doc_id = self._create_docx(title)
        node_token, wiki_doc_id = self.create_wiki_node(
            wiki_space_id,
            source_doc_id,
            title=title,
            parent_node_token=wiki_parent_node_token,
        )
        logger.info(
            "飞书Wiki挂载成功: node_token=%s, obj_token=%s, source_doc_id=%s",
            node_token,
            wiki_doc_id,
            source_doc_id,
        )
        self._sleep(1)
        self._write_blocks(wiki_doc_id, blocks)
        if wiki_doc_id != source_doc_id:
            self._delete_drive_file(source_doc_id)
        return {"url": f"https://feishu.cn/wiki/{node_token}", "node_token": node_token}

    def _create_docx(self, title: str, folder_token: str = "") -> str:
        body: dict = {"title": title}
        if folder_token:
            body["folder_token"] = folder_token
        data = self._transport.post_json(
            DOC_URL,
            body,
            "飞书文档创建失败",
            timeout=20,
        )
        doc_id = data["data"]["document"]["document_id"]
        logger.info("飞书文档创建成功: doc_id=%s, title=%s", doc_id, title)
        return doc_id

    def _delete_drive_file(self, file_token: str, file_type: str = "docx") -> None:
        response = self._transport.delete(
            DRIVE_FILE_URL.format(file_token=file_token),
            params={"type": file_type},
            timeout=10,
        )
        try:
            self._transport.parse_response(response, "飞书源文档删除失败")
        except RuntimeError as exc:
            logger.warning(str(exc))

    def _write_blocks(self, doc_id: str, blocks: list[dict]) -> None:
        if not blocks:
            logger.warning("飞书文档写入跳过: blocks为空, doc_id=%s", doc_id)
            return
        children_url = f"{DOC_URL}/{doc_id}/blocks/{doc_id}/children"
        logger.info("飞书文档写入: doc_id=%s, blocks_count=%s", doc_id, len(blocks))
        for start in range(0, len(blocks), 50):
            response = self._transport.post(
                children_url,
                json={
                    "children": blocks[start : start + 50],
                    "index": -1,
                    "document_revision_id": -1,
                },
                timeout=20,
            )
            try:
                self._transport.parse_response(
                    response,
                    f"飞书文档内容写入失败(批次 {start // 50 + 1}, 文档已创建)",
                )
            except RuntimeError as exc:
                logger.warning(str(exc))
                raise

    def create_wiki_node(
        self,
        space_id: str,
        obj_token: str,
        obj_type: str = "docx",
        title: str = "",
        parent_node_token: str = "",
    ) -> tuple[str, str]:
        body: dict = {
            "obj_type": obj_type,
            "obj_token": obj_token,
            "node_type": "origin",
        }
        if title.strip():
            body["title"] = title.strip()
        if parent_node_token.strip():
            body["parent_node_token"] = parent_node_token.strip()
        data = self._transport.post_json(
            WIKI_NODE_URL.format(space_id=space_id),
            body,
            "飞书知识库节点创建失败",
            timeout=20,
        )
        node = data["data"]["node"]
        return node["node_token"], node["obj_token"]

    def grant_doc_edit_permission(
        self,
        doc_id: str,
        receiver: str,
        doc_type: str = "docx",
    ) -> None:
        member_type = "openid" if not receiver.startswith("oc_") else "openchat"
        response = self._transport.post(
            PERMISSION_URL.format(token=doc_id),
            params={"type": doc_type, "need_notification": "false"},
            json={
                "member_type": member_type,
                "member_id": receiver,
                "perm": "full_access",
            },
            timeout=10,
        )
        try:
            self._transport.parse_response(response, "飞书文档权限授予失败")
        except RuntimeError as exc:
            logger.warning(str(exc))
            raise

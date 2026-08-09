import time
from collections.abc import Callable
from typing import Any

from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.infrastructure.http.client import get_session
from app.infrastructure.integrations.feishu.auth import FeishuAuth
from app.infrastructure.integrations.feishu.documents import FeishuDocumentClient
from app.infrastructure.integrations.feishu.messaging import FeishuMessageClient
from app.infrastructure.integrations.feishu.transport import FeishuTransport


class FeishuClient:
    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        session_provider: Callable[[], Any],
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.auth = FeishuAuth(settings_provider, session_provider)
        self.transport = FeishuTransport(self.auth, session_provider)
        self.documents = FeishuDocumentClient(
            self.transport,
            sleep=sleep,
        )
        self.messages = FeishuMessageClient(self.transport)

    def create_doc(self, *args, **kwargs) -> dict:
        return self.documents.create_doc(*args, **kwargs)

    def create_wiki_node(self, *args, **kwargs) -> tuple[str, str]:
        return self.documents.create_wiki_node(*args, **kwargs)

    def grant_doc_edit_permission(self, *args, **kwargs) -> None:
        self.documents.grant_doc_edit_permission(*args, **kwargs)

    def send_card(self, receiver: str, card: dict) -> None:
        self.messages.send_card(receiver, card)


feishu_client = FeishuClient(get_effective_settings, get_session)

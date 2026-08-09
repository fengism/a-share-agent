from collections.abc import Callable

import app.infrastructure.integrations.notion.payloads as payloads
from app.configuration.runtime import get_effective_settings
from app.configuration.schema import Settings
from app.infrastructure.http.client import get_session
from app.infrastructure.integrations.notion.schemas import NotionExportResponse
from app.infrastructure.integrations.notion.transport import NotionTransport


class NotionClient:
    def __init__(
        self,
        settings_provider: Callable[[], Settings],
        transport: NotionTransport,
    ) -> None:
        self._settings_provider = settings_provider
        self._transport = transport

    def create_page(self, title: str, blocks: list[dict]) -> NotionExportResponse:
        settings = self._settings_provider()
        parent = payloads.resolve_parent(settings)
        data = self._transport.create_page(
            settings.notion_api_token.strip(),
            {
                "parent": parent,
                "properties": payloads.page_properties(title, parent),
                "children": blocks,
            },
        )
        return NotionExportResponse(
            page_id=str(data.get("id", "")),
            url=str(data.get("url", "")),
            title=title,
        )


notion_client = NotionClient(get_effective_settings, NotionTransport(get_session))

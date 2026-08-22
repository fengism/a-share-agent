import json

from app.core.concurrency.rate_limiter import call_blocking, database_semaphore
from app.infrastructure.persistence import chat_state as chat_state_store
from app.modules.chat.schemas import ChatStateResponse, ChatStateSnapshot


class ChatStateConflictError(RuntimeError):
    pass


def _snapshot_from_record(record: chat_state_store.ChatStateRecord) -> ChatStateSnapshot:
    payload = json.loads(record.payload_json)
    payload["revision"] = record.revision
    return ChatStateSnapshot.model_validate(payload)


async def get_chat_state(user_id: int) -> ChatStateResponse:
    record = await call_blocking(chat_state_store.get_state, user_id, semaphore=database_semaphore)
    if record is None:
        return ChatStateResponse()
    return ChatStateResponse(
        state=_snapshot_from_record(record),
        updated_at=record.updated_at,
    )


async def save_chat_state(state: ChatStateSnapshot, user_id: int) -> ChatStateResponse:
    result = await call_blocking(
        chat_state_store.compare_and_swap_state,
        user_id,
        state.model_dump_json(exclude={"revision"}),
        state.revision,
        semaphore=database_semaphore,
    )
    if isinstance(result, chat_state_store.ChatStateWriteConflict):
        raise ChatStateConflictError("聊天会话已在其他页面更新")
    return ChatStateResponse(
        state=_snapshot_from_record(result.state),
        updated_at=result.state.updated_at,
    )

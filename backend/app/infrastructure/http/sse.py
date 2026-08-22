from collections.abc import Iterator

from app.infrastructure.http.client import get_provider_session


def event_stream(url: str, params: dict) -> Iterator[str]:
    """Yield decoded SSE event blocks from a blocking HTTP response."""
    with get_provider_session().get(url, params=params, stream=True, timeout=(5, 30)) as response:
        response.raise_for_status()
        event_data = ""
        for line in response.iter_lines(decode_unicode=True):
            if line:
                event_data += line + "\n"
            elif event_data:
                yield event_data
                event_data = ""
        if event_data:
            yield event_data

import json
from typing import Any

import requests

from app.config import get_settings

_session: requests.Session | None = None


def _get_session() -> requests.Session:
    """Get or lazily create a shared requests.Session respecting http_trust_env setting.

    Param:
        None
    Return:
        the shared requests.Session instance
    """
    global _session
    if _session is None:
        _session = requests.Session()
        _session.trust_env = get_settings().http_trust_env
    return _session


def _reset_session() -> None:
    """Reset the cached session; call after http_trust_env is changed at runtime."""
    global _session
    _session = None


def request(method: str, url: str, *, params: dict | None = None, data: Any = None, json_body: Any = None, headers: dict | None = None, timeout: int | float = 10) -> requests.Response:
    """Send an HTTP request and raise on non-2xx status.

    Param:
        method: HTTP method (e.g. "GET", "POST")
        url: request URL
        params: optional query parameters
        data: optional request body data
        json_body: optional JSON-serializable body
        headers: optional request headers
        timeout: request timeout in seconds (default 10)
    Return:
        the requests.Response object with a successful status
    """
    response = _get_session().request(
        method,
        url,
        params=params,
        data=data,
        json=json_body,
        headers=headers,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def get(url: str, **kwargs) -> requests.Response:
    """Send an HTTP GET request via the shared session.

    Param:
        url: request URL
        **kwargs: forwarded to request()
    Return:
        the requests.Response object
    """
    return request("GET", url, **kwargs)


def post(url: str, **kwargs) -> requests.Response:
    """Send an HTTP POST request via the shared session.

    Param:
        url: request URL
        **kwargs: forwarded to request()
    Return:
        the requests.Response object
    """
    return request("POST", url, **kwargs)


def parse_text_json(response: requests.Response) -> Any:
    """Parse the response text as JSON after stripping whitespace.

    Param:
        response: requests.Response with JSON text body
    Return:
        parsed JSON value
    """
    return json.loads(response.text.strip())

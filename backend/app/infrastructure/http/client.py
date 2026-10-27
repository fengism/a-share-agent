import json
import logging
import threading
from collections.abc import Callable
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.configuration import get_settings

logger = logging.getLogger(__name__)

_session: requests.Session | None = None
_provider_session: requests.Session | None = None
_session_lock = threading.Lock()


def _integration_retry_policy() -> Retry:
    return Retry(
        total=2,
        connect=2,
        read=2,
        backoff_factor=0.3,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        raise_on_status=False,
    )


def _provider_retry_policy() -> Retry:
    return Retry(
        total=0,
        connect=0,
        read=0,
        redirect=0,
        status=0,
        raise_on_status=False,
    )


def _build_session(retry_policy: Retry) -> requests.Session:
    session = requests.Session()
    session.trust_env = get_settings().http_trust_env
    adapter = HTTPAdapter(max_retries=retry_policy, pool_connections=20, pool_maxsize=50)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def _get_session() -> requests.Session:
    """Get or lazily create the shared integration session.

    Param:
        None
    Return:
        the shared requests.Session instance
    """
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is None:
            _session = _build_session(_integration_retry_policy())
    return _session


get_session = _get_session
"""Public alias for _get_session."""


def get_provider_session() -> requests.Session:
    """Get the pooled Provider session whose retries are owned by ProviderGateway."""
    global _provider_session
    if _provider_session is not None:
        return _provider_session
    with _session_lock:
        if _provider_session is None:
            _provider_session = _build_session(_provider_retry_policy())
    return _provider_session


def reset_session() -> None:
    """Reset both cached sessions after runtime HTTP settings change."""
    close_session()


def close_session() -> None:
    """关闭共享 HTTP 会话并释放全部连接池。"""
    global _provider_session, _session
    with _session_lock:
        sessions = (_session, _provider_session)
        _session = None
        _provider_session = None
    for session in sessions:
        if session is not None:
            session.close()


def _request_with_session(
    session_provider: Callable[[], requests.Session],
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: Any = None,
    json_body: Any = None,
    headers: dict | None = None,
    timeout: int | float | tuple[float, float] = 10,
    allow_redirects: bool = True,
    proxies: dict[str, str] | None = None,
    **kwargs: Any,
) -> requests.Response:
    request_options: dict[str, Any] = {
        "params": params,
        "data": data,
        "json": json_body,
        "headers": headers,
        "timeout": timeout,
    }
    if proxies is not None:
        request_options["proxies"] = proxies
    if not allow_redirects:
        request_options["allow_redirects"] = False
    request_options.update(kwargs)
    response = session_provider().request(method, url, **request_options)
    response.raise_for_status()
    return response


def request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    data: Any = None,
    json_body: Any = None,
    headers: dict | None = None,
    timeout: int | float = 10,
    allow_redirects: bool = True,
) -> requests.Response:
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
    return _request_with_session(
        get_session,
        method,
        url,
        params=params,
        data=data,
        json_body=json_body,
        headers=headers,
        timeout=timeout,
        allow_redirects=allow_redirects,
    )


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


def provider_request(method: str, url: str, **kwargs) -> requests.Response:
    """Send one Provider transport attempt; ProviderGateway owns retries."""
    try:
        from app.configuration import get_settings
        from app.infrastructure.http.proxy import resolve_proxy_request

        settings = get_settings()
        options = resolve_proxy_request(url, settings)
        if options.active and "proxies" not in kwargs:
            kwargs["proxies"] = options.proxies
    except Exception as exc:
        logger.debug("解析出站代理失败，使用直连: %s", exc)
    return _request_with_session(get_provider_session, method, url, **kwargs)


def provider_get(url: str, **kwargs) -> requests.Response:
    """Send one Provider GET transport attempt."""
    return provider_request("GET", url, **kwargs)


def provider_post(url: str, **kwargs) -> requests.Response:
    """Send one Provider POST transport attempt."""
    return provider_request("POST", url, **kwargs)


def parse_text_json(response: requests.Response) -> Any:
    """Parse the response text as JSON after stripping whitespace.

    Param:
        response: requests.Response with JSON text body
    Return:
        parsed JSON value
    """
    return json.loads(response.text.strip())

"""Loopback proxy that pins browser connections to validated public IP addresses."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Callable
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from app.agentic.tools.packs.web.url_security import (
    ResolvedUrlTarget,
    UnsafeUrlError,
    resolve_url_target,
    validate_url_syntax,
)

_MAX_PROXY_HEADER_BYTES = 64 * 1024
_PROXY_IO_CHUNK_BYTES = 64 * 1024
_PROXY_CONNECT_TIMEOUT_SECONDS = 10.0
_PROXY_DNS_TIMEOUT_SECONDS = 10.0
_PROXY_HEADER_TIMEOUT_SECONDS = 10.0
_MAX_CONCURRENT_DNS_LOOKUPS = 16
_MAX_CONCURRENT_PROXY_CONNECTIONS = 64
_MAX_UPSTREAM_ADDRESSES = 8
_DEFAULT_MAX_REQUEST_BYTES = 2 * 1024 * 1024
_PROXY_CLOSE_TIMEOUT_SECONDS = 1.0

logger = logging.getLogger(__name__)


class BrowserResourceLimitError(RuntimeError):
    """Raised when browser network traffic exceeds the configured budget."""


@dataclass(frozen=True, slots=True)
class BrowserProxyLimits:
    max_response_bytes: int
    max_request_bytes: int = _DEFAULT_MAX_REQUEST_BYTES

    def __post_init__(self) -> None:
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes 必须大于 0")
        if self.max_request_bytes <= 0:
            raise ValueError("max_request_bytes 必须大于 0")


class SafeBrowserProxy:
    """HTTP forward proxy with DNS pinning and a shared response-byte budget.

    Chromium sends every HTTP(S) and WebSocket connection through this loopback
    proxy. DNS is resolved once per origin, every returned address is validated,
    and the upstream socket connects directly to one of those exact addresses.
    """

    def __init__(
        self,
        *,
        limits: BrowserProxyLimits,
        resolver: Callable[[str], ResolvedUrlTarget] = resolve_url_target,
    ) -> None:
        self._limits = limits
        self._resolver = resolver
        self._server: asyncio.Server | None = None
        self._resolution_tasks: dict[tuple[str, str, int], asyncio.Task[ResolvedUrlTarget]] = {}
        self._resolution_lock = asyncio.Lock()
        self._dns_slots = asyncio.Semaphore(_MAX_CONCURRENT_DNS_LOOKUPS)
        self._connection_slots = asyncio.Semaphore(_MAX_CONCURRENT_PROXY_CONNECTIONS)
        self._budget_lock = asyncio.Lock()
        self._response_bytes = 0
        self._request_bytes = 0
        self._limit_error: BrowserResourceLimitError | None = None
        self._writers: set[asyncio.StreamWriter] = set()
        self._client_tasks: set[asyncio.Task[None]] = set()
        self._closing = False

    @property
    def url(self) -> str:
        if self._server is None or not self._server.sockets:
            raise RuntimeError("浏览器安全代理尚未启动")
        port = self._server.sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    @property
    def limit_error(self) -> BrowserResourceLimitError | None:
        return self._limit_error

    async def __aenter__(self) -> SafeBrowserProxy:
        self._server = await asyncio.start_server(
            self._handle_client,
            host="127.0.0.1",
            port=0,
            limit=_MAX_PROXY_HEADER_BYTES,
        )
        return self

    async def __aexit__(self, *_args: object) -> None:
        self._closing = True
        server, self._server = self._server, None
        if server is not None:
            server.close()
        # Stop handlers before draining writers: a pending DNS/connect must not
        # add another upstream socket after the writer snapshot is taken.
        tasks = tuple(self._client_tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        resolutions = tuple(self._resolution_tasks.values())
        for resolution_task in resolutions:
            if not resolution_task.done():
                resolution_task.cancel()
        await asyncio.gather(*resolutions, return_exceptions=True)
        self._resolution_tasks.clear()
        await asyncio.gather(*(self._close_writer(writer) for writer in tuple(self._writers)))
        self._writers.clear()
        # Python 3.12 waits for active connections here, not just the listener.
        if server is not None:
            await server.wait_closed()

    @staticmethod
    def _closed_transport_error(error: RuntimeError) -> bool:
        # uvloop uses RuntimeError rather than ConnectionError for this race.
        # Never classify an arbitrary RuntimeError as a normal disconnect.
        return "unable to perform operation on" in str(error) and "the handler is closed" in str(error)

    @classmethod
    async def _write(cls, writer: asyncio.StreamWriter, data: bytes) -> None:
        if writer.is_closing():
            raise ConnectionError("代理连接已关闭")
        try:
            writer.write(data)
            await writer.drain()
        except RuntimeError as error:
            if not cls._closed_transport_error(error):
                raise
            raise ConnectionError("代理连接在写入时关闭") from error

    @classmethod
    async def _close_writer(cls, writer: asyncio.StreamWriter) -> None:
        try:
            writer.close()
            await asyncio.wait_for(writer.wait_closed(), timeout=_PROXY_CLOSE_TIMEOUT_SECONDS)
        except TimeoutError:
            # close() may still be flushing to an unresponsive peer.
            writer.transport.abort()
        except (ConnectionError, OSError):
            pass
        except RuntimeError as error:
            if not cls._closed_transport_error(error):
                raise

    def _ensure_client_open(self, writer: asyncio.StreamWriter) -> None:
        if self._closing or writer.is_closing():
            raise ConnectionError("浏览器或代理已关闭连接")

    async def _resolve_once(self, url: str) -> ResolvedUrlTarget:
        async with self._dns_slots:
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(self._resolver, url),
                    timeout=_PROXY_DNS_TIMEOUT_SECONDS,
                )
            except TimeoutError as error:
                raise UnsafeUrlError("主机名解析超时") from error

    async def resolve(self, url: str) -> ResolvedUrlTarget:
        """Return the one cached, validated DNS result used by the proxy."""
        if self._closing:
            raise ConnectionError("浏览器安全代理正在关闭")
        scheme, hostname, port = validate_url_syntax(url)
        cache_key = (scheme, hostname, port)
        async with self._resolution_lock:
            task = self._resolution_tasks.get(cache_key)
            if task is None:
                task = asyncio.create_task(self._resolve_once(url))
                self._resolution_tasks[cache_key] = task
        try:
            return await asyncio.shield(task)
        except Exception:
            # Retain failed tasks for this browser session. A hostname that failed
            # validation must not get another DNS answer later in the same fetch.
            raise

    async def _charge_response_bytes(self, size: int) -> None:
        async with self._budget_lock:
            self._response_bytes += size
            if self._response_bytes > self._limits.max_response_bytes:
                if self._limit_error is None:
                    self._limit_error = BrowserResourceLimitError(
                        f"浏览器下载数据超过上限 {self._limits.max_response_bytes} 字节"
                    )
                raise self._limit_error

    async def _charge_request_bytes(self, size: int) -> None:
        async with self._budget_lock:
            self._request_bytes += size
            if self._request_bytes > self._limits.max_request_bytes:
                if self._limit_error is None:
                    self._limit_error = BrowserResourceLimitError(
                        f"浏览器上传数据超过上限 {self._limits.max_request_bytes} 字节"
                    )
                raise self._limit_error

    async def _open_upstream(self, target: ResolvedUrlTarget) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        last_error: OSError | None = None
        for address in target.addresses[:_MAX_UPSTREAM_ADDRESSES]:
            try:
                return await asyncio.wait_for(
                    asyncio.open_connection(address, target.port),
                    timeout=_PROXY_CONNECT_TIMEOUT_SECONDS,
                )
            except (OSError, TimeoutError) as error:
                last_error = error
        raise ConnectionError(f"无法连接已校验地址: {target.hostname}:{target.port}") from last_error

    async def _copy_stream(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        direction: str,
    ) -> None:
        while data := await reader.read(_PROXY_IO_CHUNK_BYTES):
            if direction == "response":
                await self._charge_response_bytes(len(data))
            else:
                await self._charge_request_bytes(len(data))
            await self._write(writer, data)

    async def _tunnel(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        upstream_reader: asyncio.StreamReader,
        upstream_writer: asyncio.StreamWriter,
    ) -> None:
        client_to_upstream = asyncio.create_task(self._copy_stream(client_reader, upstream_writer, direction="request"))
        upstream_to_client = asyncio.create_task(
            self._copy_stream(upstream_reader, client_writer, direction="response")
        )
        tasks = {client_to_upstream, upstream_to_client}
        try:
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                with contextlib.suppress(ConnectionError, OSError, asyncio.CancelledError):
                    task.result()
        finally:
            # Also runs when the parent handler is cancelled by proxy shutdown.
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    @staticmethod
    def _connect_url(authority: str) -> str:
        parsed = urlsplit(f"//{authority}")
        if not parsed.hostname:
            raise UnsafeUrlError("CONNECT 请求缺少主机名")
        try:
            port = parsed.port or 443
        except ValueError as error:
            raise UnsafeUrlError("CONNECT 请求端口无效") from error
        host = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
        return f"https://{host}:{port}/"

    @staticmethod
    def _prepare_http_request(request_head: bytes, request_target: str, target: ResolvedUrlTarget) -> bytes:
        lines = request_head.decode("iso-8859-1").split("\r\n")
        method, _, version = lines[0].split(" ", 2)
        parsed = urlsplit(request_target)
        path = urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
        output = [f"{method} {path} {version}"]
        connection_written = False
        host_written = False
        for line in lines[1:]:
            if not line:
                continue
            name, separator, value = line.partition(":")
            if not separator:
                raise UnsafeUrlError("代理请求头格式无效")
            lower_name = name.strip().lower()
            lower_value = value.strip().lower()
            if lower_name in {"proxy-authorization", "proxy-connection"}:
                continue
            if lower_name == "upgrade" and lower_value == "websocket":
                raise UnsafeUrlError("浏览器抓取不允许 WebSocket")
            if lower_name == "host":
                output.append(f"Host: {target.host_header}")
                host_written = True
                continue
            if lower_name == "connection":
                output.append("Connection: close")
                connection_written = True
                continue
            output.append(line)
        if not host_written:
            output.append(f"Host: {target.host_header}")
        if not connection_written:
            output.append("Connection: close")
        return ("\r\n".join(output) + "\r\n\r\n").encode("iso-8859-1")

    @classmethod
    async def _send_error(cls, writer: asyncio.StreamWriter, status: int, message: str) -> None:
        if writer.is_closing():
            return
        body = message.encode("utf-8", errors="replace")[:1024]
        # Both write() and drain() can fail; errors raised inside an except
        # block are not caught by the outer handler's other except clauses.
        with contextlib.suppress(ConnectionError, OSError):
            await cls._write(writer, (
                f"HTTP/1.1 {status} Proxy Error\r\n"
                f"Content-Type: text/plain; charset=utf-8\r\n"
                f"Content-Length: {len(body)}\r\n"
                "Connection: close\r\n\r\n".encode("ascii")
                + body
            ))

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream_writer: asyncio.StreamWriter | None = None
        response_started = False
        connection_acquired = False
        task = asyncio.current_task()
        if task is not None:
            self._client_tasks.add(task)
        self._writers.add(writer)
        try:
            self._ensure_client_open(writer)
            if self._connection_slots.locked():
                await self._send_error(writer, 503, "浏览器代理连接数超过上限")
                return
            await self._connection_slots.acquire()
            connection_acquired = True
            request_head = await asyncio.wait_for(
                reader.readuntil(b"\r\n\r\n"),
                timeout=_PROXY_HEADER_TIMEOUT_SECONDS,
            )
            if len(request_head) > _MAX_PROXY_HEADER_BYTES:
                raise UnsafeUrlError("代理请求头超过限制")
            first_line = request_head.split(b"\r\n", 1)[0].decode("iso-8859-1")
            method, request_target, _version = first_line.split(" ", 2)

            if method.upper() == "CONNECT":
                target = await self.resolve(self._connect_url(request_target))
                self._ensure_client_open(writer)
                upstream_reader, upstream_writer = await self._open_upstream(target)
                self._writers.add(upstream_writer)
                self._ensure_client_open(writer)
                response_started = True
                await self._write(writer, b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await self._tunnel(reader, writer, upstream_reader, upstream_writer)
                return

            parsed = urlsplit(request_target)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                raise UnsafeUrlError("代理仅接受绝对 http/https URL")
            if parsed.scheme.lower() == "https":
                raise UnsafeUrlError("HTTPS 请求必须使用 CONNECT 隧道")
            target = await self.resolve(request_target)
            self._ensure_client_open(writer)
            # Validate the whole header before opening an upstream socket.
            forwarded_head = self._prepare_http_request(request_head, request_target, target)
            upstream_reader, upstream_writer = await self._open_upstream(target)
            self._writers.add(upstream_writer)
            self._ensure_client_open(writer)
            await self._write(upstream_writer, forwarded_head)
            response_started = True
            await self._tunnel(reader, writer, upstream_reader, upstream_writer)
        except (UnsafeUrlError, BrowserResourceLimitError) as error:
            if not response_started and not self._closing:
                await self._send_error(writer, 403, str(error))
        except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            if not response_started and not self._closing:
                await self._send_error(writer, 400, "无效代理请求")
        except TimeoutError:
            if not response_started and not self._closing:
                await self._send_error(writer, 408, "代理请求头读取超时")
        except (ConnectionError, OSError) as error:
            logger.debug("浏览器代理连接中断: error_type=%s response_started=%s", type(error).__name__, response_started)
            if not response_started and not self._closing:
                await self._send_error(writer, 502, "代理连接中断")
        finally:
            try:
                await asyncio.gather(*(self._close_writer(stream_writer)
                                       for stream_writer in (upstream_writer, writer)
                                       if stream_writer is not None))
            finally:
                if connection_acquired:
                    self._connection_slots.release()
                for stream_writer in (upstream_writer, writer):
                    if stream_writer is not None:
                        self._writers.discard(stream_writer)
                if task is not None:
                    self._client_tasks.discard(task)

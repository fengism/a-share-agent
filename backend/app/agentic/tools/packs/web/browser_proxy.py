"""Loopback proxy that pins browser connections to validated public IP addresses."""

from __future__ import annotations

import asyncio
import contextlib
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
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        for task in self._resolution_tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self._resolution_tasks.values(), return_exceptions=True)
        self._resolution_tasks.clear()
        for writer in tuple(self._writers):
            writer.close()
        for writer in tuple(self._writers):
            with contextlib.suppress(Exception):
                await writer.wait_closed()
        self._writers.clear()

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
            writer.write(data)
            await writer.drain()

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
        done, pending = await asyncio.wait(
            {client_to_upstream, upstream_to_client},
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            with contextlib.suppress(ConnectionError, BrokenPipeError, asyncio.CancelledError):
                task.result()

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

    @staticmethod
    async def _send_error(writer: asyncio.StreamWriter, status: int, message: str) -> None:
        body = message.encode("utf-8", errors="replace")[:1024]
        writer.write(
            f"HTTP/1.1 {status} Proxy Error\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n"
            f"Content-Length: {len(body)}\r\n"
            "Connection: close\r\n\r\n".encode("ascii")
            + body
        )
        with contextlib.suppress(ConnectionError, BrokenPipeError):
            await writer.drain()

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        upstream_writer: asyncio.StreamWriter | None = None
        tunnel_established = False
        connection_acquired = False
        self._writers.add(writer)
        try:
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
                upstream_reader, upstream_writer = await self._open_upstream(target)
                self._writers.add(upstream_writer)
                writer.write(b"HTTP/1.1 200 Connection Established\r\n\r\n")
                await writer.drain()
                tunnel_established = True
                await self._tunnel(reader, writer, upstream_reader, upstream_writer)
                return

            parsed = urlsplit(request_target)
            if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
                raise UnsafeUrlError("代理仅接受绝对 http/https URL")
            if parsed.scheme.lower() == "https":
                raise UnsafeUrlError("HTTPS 请求必须使用 CONNECT 隧道")
            target = await self.resolve(request_target)
            upstream_reader, upstream_writer = await self._open_upstream(target)
            self._writers.add(upstream_writer)
            upstream_writer.write(self._prepare_http_request(request_head, request_target, target))
            await upstream_writer.drain()
            await self._tunnel(reader, writer, upstream_reader, upstream_writer)
        except (UnsafeUrlError, BrowserResourceLimitError) as error:
            if not tunnel_established:
                await self._send_error(writer, 403, str(error))
        except (ValueError, UnicodeError, asyncio.IncompleteReadError, asyncio.LimitOverrunError):
            if not tunnel_established:
                await self._send_error(writer, 400, "无效代理请求")
        except TimeoutError:
            if not tunnel_established:
                await self._send_error(writer, 408, "代理请求头读取超时")
        except (ConnectionError, OSError) as error:
            if not tunnel_established:
                await self._send_error(writer, 502, str(error))
        finally:
            if connection_acquired:
                self._connection_slots.release()
            for stream_writer in (upstream_writer, writer):
                if stream_writer is None:
                    continue
                self._writers.discard(stream_writer)
                stream_writer.close()
                with contextlib.suppress(Exception):
                    await stream_writer.wait_closed()

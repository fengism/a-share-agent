"""网页与本地 PDF 内容识别、表格解析与深度结构化提取。"""

from __future__ import annotations

import asyncio
import hashlib
import io
import logging
import random
import re
from pathlib import Path
from typing import Any

from app.configuration.paths import DATA_DIR
from app.constants.http import USER_AGENTS

logger = logging.getLogger(__name__)


def detect_content_type(content_type_header: str | None) -> str:
    """Normalize an HTTP Content-Type header."""
    if not content_type_header:
        return "unknown"
    content_type = content_type_header.split(";")[0].strip().lower()
    if "html" in content_type:
        return "html"
    if "pdf" in content_type:
        return "pdf"
    if "json" in content_type:
        return "json"
    if "xml" in content_type:
        return "xml"
    return "text"


def _format_table_as_markdown(table: list[list[str | None]]) -> str:
    """将 pdfplumber 提取的二维表格数据转换为 GitHub Flavored Markdown 表格。"""
    if not table or not any(table):
        return ""
    cleaned_rows: list[list[str]] = []
    for row in table:
        cleaned_cells = [re.sub(r"\s+", " ", str(cell or "").strip()) for cell in row]
        if any(cleaned_cells):
            cleaned_rows.append(cleaned_cells)

    if not cleaned_rows:
        return ""

    num_cols = max(len(row) for row in cleaned_rows)
    normalized_rows = [
        row + [""] * (num_cols - len(row))
        for row in cleaned_rows
    ]

    header = normalized_rows[0]
    separator = ["---"] * num_cols
    body = normalized_rows[1:]

    lines = [
        "| " + " | ".join(header) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    for row in body:
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines)


def _extract_pdf_pages_plumber(
    pdf_bytes: bytes,
    start_page: int,
    max_pages: int,
    extract_tables: bool = True,
) -> tuple[str, str, int, int]:
    """使用 pdfplumber 提取 PDF 文本与结构化表格。"""
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        total_pages = len(pdf.pages)
        if total_pages == 0:
            return "", "", 0, 0

        if start_page > total_pages:
            return "", "", total_pages, total_pages
        actual_start = max(1, start_page)
        actual_end = min(total_pages, actual_start + max_pages - 1)

        extracted_parts: list[str] = []
        doc_title = ""

        for page_idx in range(actual_start - 1, actual_end):
            page_num = page_idx + 1
            page = pdf.pages[page_idx]

            page_blocks: list[str] = []

            extracted_table_texts: set[str] = set()
            if extract_tables:
                try:
                    tables = page.extract_tables()
                    for t in tables:
                        md_table = _format_table_as_markdown(t)
                        if md_table:
                            page_blocks.append(f"```markdown\n{md_table}\n```")
                            for row in t:
                                for cell in row:
                                    if cell and str(cell).strip():
                                        extracted_table_texts.add(str(cell).strip())
                except Exception as table_err:
                    logger.debug("页面表格提取跳过: page=%d, error=%s", page_num, table_err)

            raw_text = page.extract_text() or ""
            if raw_text.strip():
                text_lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
                cleaned_lines = []
                for line in text_lines:
                    if line not in extracted_table_texts or len(line) > 20:
                        cleaned_lines.append(line)
                page_text = "\n".join(cleaned_lines)
                if page_text:
                    page_blocks.append(page_text)

            if page_blocks:
                extracted_parts.append(f"### [第 {page_num} 页 / 共 {total_pages} 页]\n" + "\n\n".join(page_blocks))

            if not doc_title and raw_text.strip():
                first_line = raw_text.strip().split("\n")[0].strip()
                if len(first_line) > 3:
                    doc_title = first_line[:80]

        full_content = "\n\n---\n\n".join(extracted_parts)
        return doc_title, full_content, total_pages, actual_end


def _extract_pdf_pages_pypdf(
    pdf_bytes: bytes,
    start_page: int,
    max_pages: int,
) -> tuple[str, str, int, int]:
    """使用 pypdf 提取 PDF 文本（作为快速兜底）。"""
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(pdf_bytes))
    total_pages = len(reader.pages)
    if total_pages == 0:
        return "", "", 0, 0

    if start_page > total_pages:
        return "", "", total_pages, total_pages
    actual_start = max(1, start_page)
    actual_end = min(total_pages, actual_start + max_pages - 1)

    extracted_parts: list[str] = []
    doc_title = ""

    for page_idx in range(actual_start - 1, actual_end):
        page_num = page_idx + 1
        page = reader.pages[page_idx]
        page_text = (page.extract_text() or "").strip()
        if page_text:
            extracted_parts.append(f"### [第 {page_num} 页 / 共 {total_pages} 页]\n{page_text}")
            if not doc_title:
                doc_title = page_text.split("\n")[0].strip()[:80]

    full_content = "\n\n---\n\n".join(extracted_parts)
    return doc_title, full_content, total_pages, actual_end


def extract_pdf_content(
    pdf_bytes: bytes,
    start_page: int = 1,
    max_pages: int = 20,
    extract_tables: bool = True,
) -> tuple[str, str, int, int]:
    """从二进制 PDF 数据中提取指定页码范围的结构化文本与表格。

    Return:
        (title, markdown_content, total_pages, actual_end_page)
    """
    try:
        title, text, total_pages, end_page = _extract_pdf_pages_plumber(
            pdf_bytes, start_page=start_page, max_pages=max_pages, extract_tables=extract_tables
        )
        if text.strip():
            return title, text, total_pages, end_page
    except Exception as exc:
        logger.info("pdfplumber 解析异常，尝试 pypdf 兜底: %s", exc)

    try:
        return _extract_pdf_pages_pypdf(pdf_bytes, start_page=start_page, max_pages=max_pages)
    except Exception as exc:
        logger.warning("pypdf 解析失败: %s", exc)
        return "", "", 0, 0


def handle_pdf_response(response: Any, url: str) -> dict[str, Any]:
    """供 web_fetch 使用：从 response.content 中提取前 5 页。"""
    pdf_bytes = response.content
    title, text, total_pages, end_page = extract_pdf_content(pdf_bytes, start_page=1, max_pages=5)
    if text:
        return _page_result({
            "url": url,
            "title": title or f"PDF 文档 ({total_pages} 页)",
            "total_pages": total_pages,
            "extracted_pages": f"1 - {end_page}",
            "content": text,
            "content_type": "pdf",
        }, 1, 5, True, 0)
    return {"url": url, "title": "", "content": "", "error": "PDF指定页未提取到文本，请更换页码或使用可选文本PDF", "error_reason": "pdf_no_text", "content_type": "pdf"}


def _resolve_local_pdf_path(url: str) -> str | None:
    """解析本地路径并校验：必须是应用数据目录内的 .pdf 文件。

    此前接受任意 file:// 或本地路径，Agent 可被诱导读取服务器任意
    PDF 文件（任意文件读取漏洞），故收窄到受控的数据目录。
    """
    raw = url[len("file://"):] if url.startswith("file://") else url
    try:
        resolved = Path(raw).expanduser().resolve()
    except (OSError, ValueError):
        return None
    data_root = Path(DATA_DIR).resolve()
    if resolved.suffix.lower() != ".pdf":
        return None
    if resolved != data_root and data_root not in resolved.parents:
        return None
    return str(resolved)


async def _read_pdf_from_local(
    url: str,
    start_page: int,
    max_pages: int,
    extract_tables: bool,
) -> dict[str, Any]:
    local_path = _resolve_local_pdf_path(url)
    if local_path is None:
        return {
            "url": url,
            "title": "",
            "content": "",
            "error": "read_pdf 仅支持 http/https 在线 PDF 链接，或应用数据目录内的本地 .pdf 路径",
        }
    try:
        with open(local_path, "rb") as f:
            pdf_bytes = f.read()
        # pdfplumber 解析是 CPU 密集的同步调用，放线程池避免阻塞事件循环
        title, content, total_pages, end_page = await asyncio.to_thread(
            extract_pdf_content,
            pdf_bytes,
            start_page=start_page,
            max_pages=max_pages,
            extract_tables=extract_tables,
        )
        return {
            "url": url,
            "title": title or local_path.split("/")[-1],
            "total_pages": total_pages,
            "extracted_pages": f"{start_page} - {end_page}",
            "content": content,
            "content_type": "pdf",
        }
    except Exception as err:
        logger.debug("读取本地 PDF 失败 url=%s: %s", url, err)
        return {"url": url, "title": "", "content": "", "error": f"读取本地 PDF 失败: {err}"}


def _pdf_http_error(url: str, reason: str, message: str) -> dict[str, Any]:
    return {"url": url, "title": "", "content": "", "error": message, "error_reason": reason}


async def _read_pdf_from_http(
    url: str,
    start_page: int,
    max_pages: int,
    extract_tables: bool,
    http_get_func: Any,
) -> dict[str, Any]:
    from app.agentic.tools.packs.web.fetcher import http_get_with_retry
    from app.agentic.tools.packs.web.scrapling import is_challenge_page

    fetch_func = http_get_func or http_get_with_retry
    headers = {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "application/pdf,*/*;q=0.8",
    }
    try:
        resp = await fetch_func(url, headers=headers, timeout=30)
        if resp.status_code >= 400:
            return {"url": url, "title": "", "content": "", "error": f"下载 PDF 失败，HTTP 状态码 {resp.status_code}"}
        pdf_bytes = resp.content
        if b"%PDF" not in pdf_bytes[:1024] and is_challenge_page(html=pdf_bytes[:8192].decode("utf-8", "ignore")):
            from app.agentic.tools.packs.web.pdf_browser import fetch_pdf_in_browser
            from app.configuration import get_settings

            if not get_settings().web_fetch_browser_enabled:
                return _pdf_http_error(
                    url, "pdf_browser_disabled", "目标网站返回访问验证页，浏览器抓取未启用，无法下载 PDF",
                )
            try:
                pdf_bytes = await fetch_pdf_in_browser(url)
            except TimeoutError:
                return _pdf_http_error(url, "pdf_browser_timeout", "目标网站访问验证或 PDF 浏览器下载超时")
            except Exception as exc:
                # Keep provider/browser internals out of user-facing audit summaries.
                logger.info("PDF 浏览器下载失败: url=%s, error=%s", url, exc)
                return _pdf_http_error(
                    url, "pdf_browser_failed", "目标网站返回访问验证页，浏览器重试未能下载 PDF；请稍后重试或更换官方 PDF 链接",
                )
        if b"%PDF" not in pdf_bytes[:1024]:
            hint = "（返回内容为 HTML 网页）" if b"<html" in pdf_bytes[:1024].lower() else ""
            return _pdf_http_error(url, "pdf_not_pdf", f"目标 URL 未返回标准 PDF 流{hint}")
        title, content, total_pages, end_page = await asyncio.to_thread(
            extract_pdf_content,
            pdf_bytes,
            start_page=start_page,
            max_pages=max_pages,
            extract_tables=extract_tables,
        )
        if not content:
            return {
                "url": url,
                "title": title or f"PDF 研报/公告 (共 {total_pages} 页)",
                "total_pages": total_pages,
                "content": "",
                "error": "PDF指定页未提取到可读文本",
                "error_reason": "pdf_no_text",
                "content_type": "pdf",
            }
        return {
            "url": url,
            "title": title or f"PDF 研报/公告 (共 {total_pages} 页)",
            "total_pages": total_pages,
            "extracted_pages": f"{start_page} - {end_page}",
            "content": content,
            "content_type": "pdf",
        }
    except Exception as exc:
        logger.info("PDF 下载与阅读失败: url=%s, error=%s", url, exc)
        return {"url": url, "title": "", "content": "", "error": f"PDF 解析失败: {exc}"}


async def execute_read_pdf(
    url: str,
    start_page: int = 1,
    max_pages: int = 20,
    extract_tables: bool = True,
    *,
    http_get_func: Any = None,
    content_offset: int = 0,
    window_hash: str = "",
) -> dict[str, Any]:
    """下载并深度阅读 PDF 研报、财报或上市公司公告正文。"""
    # http/https 在线文档（大小写、前导空白均容忍）一律走远程下载；file:// 与本地 .pdf 路径直接读盘。
    if start_page < 1 or not 1 <= max_pages <= 50 or content_offset < 0:
        return _pdf_http_error(url, "pdf_invalid_range", "start_page需>=1，max_pages需为1-50，content_offset需>=0")
    if url.strip().lower().startswith(("http://", "https://")):
        result = await _read_pdf_from_http(url, start_page, max_pages, extract_tables, http_get_func)
    else:
        result = await _read_pdf_from_local(url, start_page, max_pages, extract_tables)
    return _page_result(result, start_page, max_pages, extract_tables, content_offset, window_hash)


def _page_result(result: dict[str, Any], start: int, count: int, tables: bool, offset: int, expected_hash: str = "") -> dict[str, Any]:
    if result.get("error"):
        return result
    text = str(result.get("content") or "")
    if not text.strip() or offset >= len(text):
        return {**result, "content": "", "error": "PDF页窗口无可读正文或续读偏移已失效", "error_reason": "pdf_no_text"}
    digest = hashlib.sha256(text.encode()).hexdigest()
    if expected_hash and expected_hash != digest:
        return {**result, "content": "", "error": "PDF页窗口内容已变化，请从该窗口起点重新读取", "error_reason": "pdf_window_changed"}
    total = int(result.get("total_pages") or 0)
    end = min(total, start + count - 1)
    return {
        **result, "content": text[offset:], "start_page": start, "max_pages": count, "window_hash": digest,
        "extract_tables": tables, "content_offset": offset,
        "next_read": {"start_page": end + 1, "max_pages": count, "extract_tables": tables, "content_offset": 0} if end < total else None,
        "page_scope_note": "extracted_pages为提取窗口；若发生输出截断，按next_read续读；不代表阅读全文",
    }

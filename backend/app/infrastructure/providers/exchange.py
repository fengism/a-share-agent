"""Official SSE, SZSE, and BSE stock-list providers."""

import json
import re
import xml.etree.ElementTree as ET
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from typing import Any
from urllib.parse import urlencode, urlsplit

import pandas as pd
import urllib3

from app.infrastructure.http.client import provider_get, provider_post

SSE_STOCK_LIST_URL = "https://query.sse.com.cn/sseQuery/commonQuery.do"
SZSE_STOCK_LIST_URL = "https://www.szse.cn/api/report/ShowReport/data"
SZSE_STOCK_LIST_XLSX_URL = "https://www.szse.cn/api/report/ShowReport"
BSE_STOCK_LIST_URL = "https://www.bse.cn/nqxxController/nqxxCnzq.do"
_REQUEST_TIMEOUT_SECONDS = 5
_SZSE_REQUEST_TIMEOUT_SECONDS = 3
_SZSE_HOST = "www.szse.cn"
# Official CDN addresses returned by independent public DNS resolvers. TLS is still verified for www.szse.cn.
_SZSE_CDN_IPS = ("59.36.189.138", "113.108.107.138")
_szse_preferred_cdn_ip: str | None = None
_MAX_PAGES = 50

_SSE_COLUMNS = ["证券代码", "证券简称", "上市日期", "所属行业", "板块"]
_SZSE_COLUMNS = [
    "A股代码",
    "A股简称",
    "A股上市日期",
    "所属行业",
    "A股总股本",
    "A股流通股本",
    "板块",
]
_BSE_COLUMNS = ["证券代码", "证券简称", "上市日期", "所属行业", "总股本", "流通股本"]
_SZSE_XLSX_HEADERS = {
    "板块": "bk",
    "证券类别": "bk",
    "A股代码": "agdm",
    "A股证券代码": "agdm",
    "证券代码": "agdm",
    "A股简称": "agjc",
    "A股证券简称": "agjc",
    "证券简称": "agjc",
    "A股上市日期": "agssrq",
    "上市日期": "agssrq",
    "A股总股本": "agzgb",
    "总股本": "agzgb",
    "A股流通股本": "agltgb",
    "流通股本": "agltgb",
    "所属行业": "sshymc",
    "行业": "sshymc",
}
_XLSX_MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
_XLSX_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_XLSX_PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


@dataclass(frozen=True)
class _SzseResponse:
    content: bytes

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def json(self) -> Any:
        return json.loads(self.content)


def _request_szse_cdn(
    url: str,
    *,
    params: Mapping[str, str],
    headers: Mapping[str, str],
    timeout: float,
    preferred_ip: str | None = None,
) -> _SzseResponse:
    global _szse_preferred_cdn_ip
    parsed = urlsplit(url)
    path = parsed.path or "/"
    if params:
        path = f"{path}?{urlencode(dict(params))}"
    candidates = list(dict.fromkeys([preferred_ip, *_SZSE_CDN_IPS]))
    errors: list[str] = []
    for ip in (candidate for candidate in candidates if candidate):
        pool = urllib3.HTTPSConnectionPool(
            ip,
            port=443,
            assert_hostname=_SZSE_HOST,
            server_hostname=_SZSE_HOST,
            cert_reqs="CERT_REQUIRED",
            timeout=timeout,
            retries=False,
        )
        try:
            response = pool.request(
                "GET",
                path,
                headers={**dict(headers), "Host": _SZSE_HOST},
            )
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status}")
            _szse_preferred_cdn_ip = ip
            return _SzseResponse(content=bytes(response.data))
        except Exception as error:
            errors.append(f"{ip}: {type(error).__name__}")
        finally:
            pool.close()
    raise ConnectionError(f"深交所官方 CDN 节点不可用: {', '.join(errors)}")


def _szse_get(url: str, **kwargs) -> Any:
    global _szse_preferred_cdn_ip
    params = kwargs.get("params") or {}
    headers = kwargs.get("headers") or {}
    timeout = float(kwargs.get("timeout", _SZSE_REQUEST_TIMEOUT_SECONDS))
    if _szse_preferred_cdn_ip is not None:
        try:
            return _request_szse_cdn(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
                preferred_ip=_szse_preferred_cdn_ip,
            )
        except Exception:
            _szse_preferred_cdn_ip = None
    try:
        return provider_get(url, **kwargs)
    except Exception as primary_error:
        try:
            return _request_szse_cdn(
                url,
                params=params,
                headers=headers,
                timeout=timeout,
            )
        except Exception as cdn_error:
            raise ConnectionError(
                f"深交所系统 DNS 与官方 CDN 均不可用: primary={type(primary_error).__name__}, "
                f"cdn={cdn_error}"
            ) from primary_error


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", "", str(value))
    text = re.sub(r"\s+", " ", text).strip()
    return None if not text or text in {"-", "--", "null", "None", "N/A"} else text


def _first_value(row: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return value
    return None


def _normalize_date(value: Any) -> str | None:
    text = _clean_text(value)
    if text is None:
        return None
    digits = re.sub(r"\D", "", text)
    return digits[:8] if len(digits) >= 8 else text


def _parse_number(value: Any) -> float | None:
    text = _clean_text(value)
    if text is None:
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _parse_szse_share_count(value: Any) -> float | None:
    number = _parse_number(value)
    if number is None:
        return None
    return number * 100_000_000 if abs(number) <= 10_000 else number


def _positive_int(value: Any, default: int = 1) -> int:
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _first_report_table(payload: Any) -> Mapping[str, Any]:
    if isinstance(payload, list) and payload and isinstance(payload[0], Mapping):
        return payload[0]
    if isinstance(payload, Mapping):
        return payload
    raise ValueError("交易所返回了无法识别的表格数据")


def _parse_jsonp_tables(text: str) -> Any:
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        raise ValueError("北交所返回了无法识别的 JSONP 数据")
    return json.loads(text[start : end + 1])


def _deduplicate(frame: pd.DataFrame, code_column: str, columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=columns)
    result = frame.dropna(subset=[code_column]).drop_duplicates(subset=[code_column], keep="first")
    return result.reindex(columns=columns).reset_index(drop=True)


def _normalize_szse_record(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "A股代码": _clean_text(_first_value(row, "agdm", "A股代码", "证券代码")),
        "A股简称": _clean_text(_first_value(row, "agjc", "A股简称", "证券简称")),
        "A股上市日期": _normalize_date(_first_value(row, "agssrq", "A股上市日期", "上市日期")),
        "所属行业": _clean_text(_first_value(row, "sshymc", "所属行业", "行业")),
        "A股总股本": _parse_szse_share_count(_first_value(row, "agzgb", "A股总股本", "总股本")),
        "A股流通股本": _parse_szse_share_count(
            _first_value(row, "agltgb", "A股流通股本", "流通股本")
        ),
        "板块": _clean_text(_first_value(row, "bk", "板块")),
    }


def _xlsx_column_index(reference: str | None) -> int | None:
    if not reference:
        return None
    match = re.match(r"([A-Z]+)", reference)
    if match is None:
        return None
    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _xlsx_cell_text(cell: ET.Element, shared_strings: Sequence[str]) -> str:
    cell_type = cell.get("t")
    if cell_type == "inlineStr":
        parts = [node.text or "" for node in cell.findall(f".//{{{_XLSX_MAIN_NS}}}t")]
        return re.sub(r"\s+", " ", "".join(parts)).strip()
    value_node = cell.find(f"{{{_XLSX_MAIN_NS}}}v")
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError):
            return ""
    return re.sub(r"\s+", " ", value).strip()


def _read_xlsx_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    return [
        "".join(node.text or "" for node in item.findall(f".//{{{_XLSX_MAIN_NS}}}t"))
        for item in root.findall(f"{{{_XLSX_MAIN_NS}}}si")
    ]


def _first_xlsx_sheet_path(archive: zipfile.ZipFile) -> str:
    fallback = "xl/worksheets/sheet1.xml"
    if "xl/workbook.xml" not in archive.namelist():
        return fallback
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    first_sheet = workbook.find(f".//{{{_XLSX_MAIN_NS}}}sheet")
    relationship_id = None if first_sheet is None else first_sheet.get(f"{{{_XLSX_REL_NS}}}id")
    if not relationship_id or "xl/_rels/workbook.xml.rels" not in archive.namelist():
        return fallback
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    for relationship in relationships.findall(f"{{{_XLSX_PACKAGE_REL_NS}}}Relationship"):
        if relationship.get("Id") != relationship_id:
            continue
        target = relationship.get("Target", "")
        return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    return fallback


def _read_xlsx_rows(root: ET.Element, shared_strings: Sequence[str]) -> list[list[str]]:
    sheet_data = root.find(f".//{{{_XLSX_MAIN_NS}}}sheetData")
    if sheet_data is None:
        return []
    rows: list[list[str]] = []
    for row_node in sheet_data.findall(f"{{{_XLSX_MAIN_NS}}}row"):
        values: list[str] = []
        next_index = 0
        for cell in row_node.findall(f"{{{_XLSX_MAIN_NS}}}c"):
            column_index = _xlsx_column_index(cell.get("r")) or next_index
            while len(values) < column_index:
                values.append("")
            values.append(_xlsx_cell_text(cell, shared_strings))
            next_index = column_index + 1
        while values and not values[-1]:
            values.pop()
        rows.append(values)
    return rows


def _parse_szse_xlsx_rows(content: bytes) -> list[dict[str, str]]:
    try:
        with zipfile.ZipFile(BytesIO(content)) as archive:
            shared_strings = _read_xlsx_shared_strings(archive)
            sheet_root = ET.fromstring(archive.read(_first_xlsx_sheet_path(archive)))
    except (KeyError, ET.ParseError, zipfile.BadZipFile) as error:
        raise ValueError("深交所 XLSX 名录格式无效") from error

    header_map: dict[int, str] = {}
    records: list[dict[str, str]] = []
    for values in _read_xlsx_rows(sheet_root, shared_strings):
        if not values:
            continue
        if not header_map:
            header_map = {
                index: field
                for index, value in enumerate(values)
                if (field := _SZSE_XLSX_HEADERS.get(re.sub(r"\s+", "", value)))
            }
            if {"agdm", "agjc"}.issubset(header_map.values()):
                continue
            header_map = {}
            continue
        row = {
            field: values[index]
            for index, field in header_map.items()
            if index < len(values) and values[index]
        }
        symbol = _clean_text(row.get("agdm"))
        if symbol and symbol.isdigit():
            records.append(row)
    if not records:
        raise ValueError("深交所 XLSX 名录未包含股票记录")
    return records


class OfficialExchangeProvider:
    """Load listed-stock metadata directly from the three official exchanges."""

    name = "exchange"

    def fetch_stock_names_sh(self, code: str | None = None) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        stock_types = (("8",) if code and code.startswith(("688", "689")) else ("1",)) if code else ("1", "8")
        for stock_type in stock_types:
            page_no = 1
            page_count = 1
            while page_no <= min(page_count, _MAX_PAGES):
                response = provider_get(
                    SSE_STOCK_LIST_URL,
                    params={
                        "isPagination": "true",
                        "pageHelp.cacheSize": "1",
                        "pageHelp.beginPage": str(page_no),
                        "pageHelp.pageSize": "500",
                        "pageHelp.pageNo": str(page_no),
                        "sqlId": "COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L",
                        "STOCK_TYPE": stock_type,
                        "REG_PROVINCE": "",
                        "CSRC_CODE": "",
                        "STOCK_CODE": code or "",
                        "COMPANY_STATUS": "1,2,3,4,5,6,7,8",
                        "type": "inParams",
                    },
                    headers={
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "Referer": "https://www.sse.com.cn/assortment/stock/list/share/",
                        "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
                    },
                    timeout=_REQUEST_TIMEOUT_SECONDS,
                )
                payload = response.json()
                page_help = payload.get("pageHelp", {}) if isinstance(payload, Mapping) else {}
                page_count = _positive_int(page_help.get("pageCount"))
                rows = page_help.get("data") or []
                if not isinstance(rows, list) or not rows:
                    break
                for row in rows:
                    if not isinstance(row, Mapping) or _clean_text(row.get("DELIST_DATE")):
                        continue
                    records.append(
                        {
                            "证券代码": _clean_text(row.get("A_STOCK_CODE")),
                            "证券简称": _clean_text(row.get("SEC_NAME_CN")),
                            "上市日期": _normalize_date(row.get("LIST_DATE")),
                            "所属行业": _clean_text(row.get("CSRC_CODE_DESC")),
                            "板块": {"1": "主板", "2": "科创板", "8": "科创板"}.get(
                                str(row.get("LIST_BOARD") or stock_type),
                                _clean_text(row.get("LIST_BOARD")),
                            ),
                        }
                    )
                page_no += 1
        return _deduplicate(pd.DataFrame(records), "证券代码", _SSE_COLUMNS)

    def _fetch_szse_xlsx_records(self) -> list[dict[str, Any]]:
        response = _szse_get(
            SZSE_STOCK_LIST_XLSX_URL,
            params={
                "SHOWTYPE": "xlsx",
                "CATALOGID": "1110",
                "TABKEY": "tab1",
                "random": f"{datetime.now().timestamp():.6f}",
            },
            headers={
                "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*;q=0.8",
                "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
                "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
            },
            timeout=_SZSE_REQUEST_TIMEOUT_SECONDS,
        )
        return [_normalize_szse_record(row) for row in _parse_szse_xlsx_rows(response.content)]

    def _fetch_szse_json_records(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        page_no = 1
        page_count = 1
        while page_no <= min(page_count, _MAX_PAGES):
            response = _szse_get(
                SZSE_STOCK_LIST_URL,
                params={
                    "SHOWTYPE": "JSON",
                    "CATALOGID": "1110",
                    "TABKEY": "tab1",
                    "PAGENO": str(page_no),
                    "PAGESIZE": "500",
                    "random": f"{datetime.now().timestamp():.6f}",
                },
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://www.szse.cn/market/product/stock/list/index.html",
                    "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
                },
                timeout=_SZSE_REQUEST_TIMEOUT_SECONDS,
            )
            table = _first_report_table(response.json())
            metadata = table.get("metadata")
            page_count = _positive_int(metadata.get("pagecount") if isinstance(metadata, Mapping) else None)
            rows = table.get("data") or []
            if not isinstance(rows, list) or not rows:
                break
            records.extend(_normalize_szse_record(row) for row in rows if isinstance(row, Mapping))
            page_no += 1
        return records

    def fetch_stock_names_sz(self) -> pd.DataFrame:
        try:
            records = self._fetch_szse_xlsx_records()
        except Exception:
            records = self._fetch_szse_json_records()
        return _deduplicate(pd.DataFrame(records), "A股代码", _SZSE_COLUMNS)

    def fetch_stock_names_bj(self, code: str | None = None) -> pd.DataFrame:
        records: list[dict[str, Any]] = []
        page_no = 0
        page_count = 1
        while page_no < min(page_count, _MAX_PAGES):
            response = provider_post(
                BSE_STOCK_LIST_URL,
                data={
                    "page": str(page_no),
                    "typejb": "T",
                    "xxfcbj[]": "2",
                    "xxzqdm": code or "",
                    "sortfield": "xxzqdm",
                    "sorttype": "asc",
                },
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Referer": "https://www.bse.cn/nq/listedcompany.html",
                    "User-Agent": "Mozilla/5.0 AShareAgent/1.0",
                    "Content-Type": "application/x-www-form-urlencoded",
                },
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            table = _first_report_table(_parse_jsonp_tables(response.text))
            page_count = _positive_int(table.get("totalPages"))
            rows = table.get("content") or []
            if not isinstance(rows, list) or not rows:
                break
            for row in rows:
                if not isinstance(row, Mapping) or _clean_text(row.get("xxzzrq")):
                    continue
                records.append(
                    {
                        "证券代码": _clean_text(row.get("xxzqdm")),
                        "证券简称": _clean_text(row.get("xxzqjc")),
                        "上市日期": _normalize_date(_first_value(row, "xxgprq", "fxssrq")),
                        "所属行业": _clean_text(row.get("xxhyzl")),
                        "总股本": _parse_number(row.get("xxzgb")),
                        "流通股本": _parse_number(row.get("xxfxsgb")),
                    }
                )
            page_no += 1
        return _deduplicate(pd.DataFrame(records), "证券代码", _BSE_COLUMNS)


exchange_provider = OfficialExchangeProvider()

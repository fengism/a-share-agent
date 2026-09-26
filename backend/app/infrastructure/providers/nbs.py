"""National Bureau of Statistics UUID-based macro-data provider."""

from __future__ import annotations

import csv
import math
import os
import re
import time
from collections.abc import Mapping
from datetime import datetime
from io import BytesIO, StringIO
from typing import Any, cast
from urllib.parse import urljoin

import pandas as pd
import requests

from app.core.market import market_today
from app.infrastructure.http.client import provider_get, provider_post

API_BASE = "https://data.stats.gov.cn/dg/website/publicrelease/web/external"
DATA_ENDPOINT_CANDIDATES = ("stream/esData", "getEsDataByCidAndDt")
ROOT_MONTHLY = "fc982599aa684be7969d7b90b1bd0e84"
ROOT_QUARTERLY = "a94b8b7365a94874968cabbe392cf679"
_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://data.stats.gov.cn/dg/website/page.html",
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
}
_TIMEOUT_SECONDS = 15
_LPR_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-currency/LprChrtCSV"
_LPR_START_DATE = "2019-01-01"
_PBC_BASE_URL = "https://www.pbc.gov.cn"
_PBC_INDEX_URL = f"{_PBC_BASE_URL}/diaochatongjisi/116219/116319/index.html"
_PBC_DOWNLOAD_TIMEOUT_SECONDS = 60
_PBC_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/vnd.ms-excel,*/*",
    "Referer": _PBC_INDEX_URL,
    "User-Agent": _HEADERS["User-Agent"],
}
_PBC_SOCIAL_FINANCING_COLUMNS = (
    "month",
    "afre_total",
    "rmb_loans",
    "fx_loans",
    "entrusted_loans",
    "trust_loans",
    "undiscounted_bankers_acceptance",
    "corporate_bonds",
    "government_bonds",
    "equity_financing",
    "abs_by_depository",
    "loans_written_off",
)
_SHIBOR_URL = "https://www.chinamoney.com.cn/ags/ms/cm-u-bk-shibor/ShiborHis"
_SHIBOR_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.chinamoney.com.cn/",
    "User-Agent": _HEADERS["User-Agent"],
}
_SHIBOR_TERMS = (
    ("ON", "O/N"),
    ("1W", "1W"),
    ("2W", "2W"),
    ("1M", "1M"),
    ("3M", "3M"),
    ("6M", "6M"),
    ("9M", "9M"),
    ("1Y", "1Y"),
)
_ENGLISH_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_TRADE_CID = "7e11b47c828d4e4e925f1c5a98305558"
_TRADE_SERIES = {
    "EXIT_BASE": "9e38b39f55a7461ea195508c1bb7dbdc",
    "EXIT_BASE_SAME": "788f44b0f310403fbd308b77d6f83890",
    "EXIT_ACCUMULATE": "a349b30535404467b37e68871e99762c",
    "EXIT_ACCUMULATE_SAME": "d857d76d08af4f3b92b24fa29e0ca177",
    "IMPORT_BASE": "86a340fee806409ebdf4d0069bd23f29",
    "IMPORT_BASE_SAME": "cc1ac699bc4f4cd7aa5c2b7a1e643259",
    "IMPORT_ACCUMULATE": "6545926705124075961bf28602fd50bb",
    "IMPORT_ACCUMULATE_SAME": "5273a0f169234ea5abfa6d966cb0e93a",
}
_NBS_MONTHLY_GROUPS = {
    "industrial_production": (
        (
            "3f2e14f0542348ed9fe02476eca3450b",
            {
                "VALUE_ADDED_YOY": "ef1b1765960d45a29b4d7c4ca91be916",
                "VALUE_ADDED_ACCUMULATE_YOY": "21e7072e9f384209aedb56e69a18216e",
            },
        ),
    ),
    "retail_sales": (
        (
            "d0cb882c7f27443ab6b3ef9421901961",
            {
                "RETAIL_VALUE": "1142a3a03e9045959e606a21822641ac",
                "RETAIL_ACCUMULATE": "260a1794443b43dd93a59928b12f38af",
                "RETAIL_YOY": "aaac57d54d2e465d91bc9f3ea1a8618e",
                "RETAIL_ACCUMULATE_YOY": "e3ca151b53d347b78d1e179e5ebf1d33",
            },
        ),
    ),
    "fixed_asset_investment": (
        (
            "5129067b149d4ddfbec1ffc478d35bfb",
            {
                "INVESTMENT_ACCUMULATE_YOY": "7e570cf8071c4734a7d78d9f0a70fbe1",
            },
        ),
    ),
    "real_estate": (
        (
            "9206137ccf03460daa74b7799e0f3c31",
            {
                "DEVELOPMENT_INVESTMENT": "bfb626c0dfa04afab67937c452ca9f50",
                "DEVELOPMENT_INVESTMENT_YOY": "205e08cba8c2409980db58c98da91b6f",
            },
        ),
        (
            "0ae633cdb85f4a8397650831b2b27e50",
            {
                "SALES_AREA": "d353226cf0434c929b6299f8d4987754",
                "SALES_AREA_YOY": "50a37fbef1d04be68f15d82b711783bf",
            },
        ),
        (
            "5530aa75038249fab2e5e10a9997c18b",
            {
                "SALES_VALUE": "090ed0c087024014a7fe903e409958df",
                "SALES_VALUE_YOY": "4617f4bb61234af9ab075b3695a1f0bf",
            },
        ),
    ),
    "employment": (
        (
            "ee3b7046b390415b9b7745e3d16f6052",
            {
                "URBAN_SURVEYED_UNEMPLOYMENT": "3888eac6062945a79c8a27e5f13d4953",
                "CITY31_SURVEYED_UNEMPLOYMENT": "1d550f3ec77a463bb607d4a3427e1465",
            },
        ),
    ),
}


class NbsEndpointError(ConnectionError):
    pass


class NbsWafError(ConnectionError):
    pass


class NbsApiError(RuntimeError):
    pass


class NbsEmptyDataError(ConnectionError):
    pass


class ChinaMoneyApiError(RuntimeError):
    pass


class ChinaMoneyEmptyDataError(ConnectionError):
    pass


class PbocApiError(RuntimeError):
    pass


class PbocEmptyDataError(ConnectionError):
    pass


_SERIES = {
    "CPI_YOY": {
        "freq": "month",
        "leaves": (
            ("5c7452825c7c4dcba391db5ca7f335c5", "53180dfb9c14411ba4b762307c85920c", 2026, None),
            ("809d2522b0fe4be89142650341b19083", "4ae9047687934a6390984c21d6ddab96", 2021, 2025),
        ),
    },
    "CPI_MOM": {
        "freq": "month",
        "leaves": (
            ("b4fad2cf9e0e4af7815b7e9e2e95c5c7", "f3904a1f5a384d54a3944ec6e2df3d1c", 2026, None),
            ("e6664817f0cd427783cd397770695634", "e437d965279d41ceb9ace591b62f6ffc", 2021, 2025),
        ),
    },
    "PPI_YOY": {
        "freq": "month",
        "leaves": (("60e8b361f11c4a878c652a6487a25561", "150633e52b9a470a9a9fd1b296dd6c5b", 1996, None),),
    },
    "PMI_MANUFACTURING": {
        "freq": "month",
        "leaves": (("93ffbb1aa85740d3aa2618371508b606", "a09aa989bdcf4cffa2021795722eb916", 2005, None),),
    },
    "PMI_NON_MANUFACTURING": {
        "freq": "month",
        "leaves": (("7a64a6e25aec4a8e9dde044ecd9e2cce", "88a150208f6e4a1db8babe41ae700f66", 2007, None),),
    },
    "M2": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "f3c0ae453a54424489af41de315ec592", 1999, None),),
    },
    "M2_YOY": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "e03f2232631f41cd9d754a7d7feb4a81", 1999, None),),
    },
    "M1": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "add08d4a1ca049158166f126e169edde", 1999, None),),
    },
    "M1_YOY": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "640401d3351b4b868dea28f89f410a54", 1999, None),),
    },
    "M0": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "bd67997414b147a08d4aa03d146f4486", 1999, None),),
    },
    "M0_YOY": {
        "freq": "month",
        "leaves": (("82130c6621a745cda3d64b090e733383", "db7891fb8f3c4eb2a4d71a9955eba8c7", 1999, None),),
    },
    "GDP_NOMINAL_Q": {
        "freq": "quarter",
        "leaves": (("28d936104e304aa191e338eb82b6dc09", "d22612f09aeb4241bc557ef0ac61b3ba", 1992, None),),
    },
    "GDP_INDEX_Q": {
        "freq": "quarter",
        "leaves": (("f9b694c9b79e4ce5958bc88c6410fa67", "170e7f00f8c24ede863c0526b42ae81f", 1992, None),),
    },
}


def _data_urls() -> list[str]:
    override = os.getenv("NBSC_DATA_URL", "").strip()
    if override:
        return [override]
    return [f"{API_BASE}/{endpoint}" for endpoint in DATA_ENDPOINT_CANDIDATES]


def _period_label(code: str, freq: str) -> str | None:
    digits = re.sub(r"[A-Za-z]+$", "", code)
    if freq == "quarter" and len(digits) >= 6:
        quarter = int(digits[4:6])
        return f"{digits[:4]}Q{quarter}" if 1 <= quarter <= 4 else None
    if freq == "month" and len(digits) >= 6:
        return f"{digits[:4]}-{digits[4:6]}"
    return None


def _shibor_history_window() -> tuple[datetime, datetime]:
    end_date = datetime.now()
    start_month_index = end_date.year * 12 + end_date.month - 1 - 2
    start_year, start_month = divmod(start_month_index, 12)
    return end_date.replace(year=start_year, month=start_month + 1, day=1), end_date


def _format_chinamoney_date(value: datetime) -> str:
    return f"{value.day:02d} {_ENGLISH_MONTHS[value.month - 1]} {value.year}"


def _pbc_get(url: str, *, timeout: int = _TIMEOUT_SECONDS) -> Any:
    response = provider_get(
        url,
        headers=_PBC_HEADERS,
        timeout=timeout,
    )
    response.raise_for_status()
    return response


def _pbc_get_text(url: str) -> str:
    response = _pbc_get(url)
    apparent_encoding = getattr(response, "apparent_encoding", None)
    if apparent_encoding:
        response.encoding = apparent_encoding
    return str(response.text)


def _pbc_month_label(value: Any) -> str | None:
    """Convert PBOC workbook month cells while preserving October's dropped zero."""
    match = re.fullmatch(r"(\d{4})\.(\d{1,2})", str(value).strip())
    if match is None:
        return None
    year, month = match.groups()
    if len(month) == 1:
        month += "0"
    month_number = int(month)
    if not 1 <= month_number <= 12:
        return None
    return f"{year}-{month_number:02d}"


def _optional_float(value: Any) -> float | None:
    if value is None or bool(pd.isna(value)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def fetch_series_batch(
    cid: str,
    indicator_ids: tuple[str, ...],
    dts: str,
    *,
    freq: str = "month",
) -> dict[str, dict[str, float]]:
    if not indicator_ids:
        raise ValueError("国家统计局指标列表不能为空")
    body = {
        "cid": cid,
        "indicatorIds": list(indicator_ids),
        "daCatalogId": "",
        "das": [{"text": "全国", "value": "000000000000"}],
        "showType": "1",
        "dts": [dts],
        "rootId": ROOT_QUARTERLY if freq == "quarter" else ROOT_MONTHLY,
    }
    response = None
    attempted_urls: list[str] = []
    for url in _data_urls():
        attempted_urls.append(url)
        try:
            response = provider_post(
                url,
                json_body=body,
                headers=_HEADERS,
                timeout=_TIMEOUT_SECONDS,
            )
        except requests.HTTPError as error:
            status = error.response.status_code if error.response is not None else None
            if status in {404, 405}:
                continue
            raise
        if response.status_code in {404, 405}:
            continue
        response.raise_for_status()
        break
    if response is None or response.status_code in {404, 405}:
        raise NbsEndpointError(f"国家统计局数据接口已改名: {attempted_urls}")
    headers = getattr(response, "headers", {})
    if headers.get("Content-Type", "").lower().startswith("text/html"):
        raise NbsWafError("国家统计局返回 WAF HTML 页面")
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("state") != 20000:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise NbsApiError(f"国家统计局 API 异常: {message or payload}")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise NbsEmptyDataError(f"国家统计局指标数据为空: cid={cid}, dts={dts}")
    result: dict[str, dict[str, float]] = {indicator_id: {} for indicator_id in indicator_ids}
    for block in data:
        if not isinstance(block, Mapping):
            continue
        period = _period_label(str(block.get("code") or ""), freq)
        values = block.get("values")
        if period is None or not isinstance(values, list):
            continue
        for item in values:
            if not isinstance(item, Mapping) or item.get("value") in {None, ""}:
                continue
            indicator_id = str(item.get("_id") or "")
            if not indicator_id and len(indicator_ids) == 1:
                indicator_id = indicator_ids[0]
            if indicator_id in result:
                result[indicator_id][period] = float(item["value"])
    if not any(result.values()):
        raise NbsEmptyDataError(f"国家统计局指标值为空: cid={cid}, dts={dts}")
    return result


def fetch_series(
    cid: str,
    indicator_id: str,
    dts: str,
    *,
    freq: str = "month",
) -> dict[str, float]:
    return fetch_series_batch(cid, (indicator_id,), dts, freq=freq)[indicator_id]


class NbsDataProvider:
    name = "nbs"

    def _load_series(self, name: str) -> dict[str, float]:
        spec = cast(dict[str, Any], _SERIES[name])
        freq = str(spec["freq"])
        leaves = cast(tuple[tuple[str, str, int, int | None], ...], spec["leaves"])
        current_year = market_today().year
        requested_start = current_year - 2
        requested_end = current_year
        merged: dict[str, float] = {}
        for cid, indicator_id, start, end in leaves:
            leaf_end = int(end) if end is not None else requested_end
            effective_start = max(requested_start, int(start))
            effective_end = min(requested_end, leaf_end)
            if effective_start > effective_end:
                continue
            suffix = "SS" if freq == "quarter" else "MM"
            start_period = "01"
            end_period = "04" if freq == "quarter" else "12"
            dts = f"{effective_start}{start_period}{suffix}-{effective_end}{end_period}{suffix}"
            merged.update(fetch_series(str(cid), str(indicator_id), dts, freq=freq))
        if not merged:
            raise NbsEmptyDataError(f"国家统计局序列为空: {name}")
        return merged

    @staticmethod
    def _change_from_index(value: float | None) -> float | None:
        return round(value - 100, 6) if value is not None else None

    def _fetch_monthly_group(self, name: str) -> list[dict[str, Any]]:
        groups = _NBS_MONTHLY_GROUPS.get(name)
        if groups is None:
            raise ValueError(f"不支持的国家统计局月度指标组: {name}")

        current_year = market_today().year
        dts = f"{current_year - 2}01MM-{current_year}12MM"
        values_by_field: dict[str, dict[str, float]] = {}
        for cid, fields in groups:
            values_by_indicator = fetch_series_batch(
                cid,
                tuple(fields.values()),
                dts,
            )
            values_by_field.update(
                {
                    field: values_by_indicator[indicator_id]
                    for field, indicator_id in fields.items()
                }
            )

        periods = set().union(*(values.keys() for values in values_by_field.values()))
        return [
            {
                "TIME": period,
                **{
                    field: values.get(period)
                    for field, values in values_by_field.items()
                },
            }
            for period in sorted(periods, reverse=True)
        ]

    def fetch_china_cpi(self) -> list[dict[str, Any]]:
        yoy = self._load_series("CPI_YOY")
        mom = self._load_series("CPI_MOM")
        return [
            {
                "TIME": period,
                "NATIONAL_SAME": self._change_from_index(yoy.get(period)),
                "NATIONAL_SEQUENTIAL": self._change_from_index(mom.get(period)),
            }
            for period in sorted(set(yoy) | set(mom), reverse=True)
        ]

    def fetch_china_ppi(self) -> list[dict[str, Any]]:
        yoy = self._load_series("PPI_YOY")
        return [
            {
                "TIME": period,
                "BASE": self._change_from_index(value),
                "BASE_SAME": self._change_from_index(value),
            }
            for period, value in sorted(yoy.items(), reverse=True)
        ]

    def fetch_china_pmi(self) -> list[dict[str, Any]]:
        manufacturing = self._load_series("PMI_MANUFACTURING")
        non_manufacturing = self._load_series("PMI_NON_MANUFACTURING")
        return [
            {
                "TIME": period,
                "MAKE_INDEX": manufacturing.get(period),
                "NMAKE_INDEX": non_manufacturing.get(period),
            }
            for period in sorted(set(manufacturing) | set(non_manufacturing), reverse=True)
        ]

    def fetch_china_economy_currency_supply(self) -> list[dict[str, Any]]:
        series = {name: self._load_series(name) for name in ("M2", "M2_YOY", "M1", "M1_YOY", "M0", "M0_YOY")}
        periods = set().union(*(values.keys() for values in series.values()))
        return [
            {
                "TIME": period,
                "BASIC_CURRENCY": series["M2"].get(period),
                "BASIC_CURRENCY_SAME": series["M2_YOY"].get(period),
                "CURRENCY": series["M1"].get(period),
                "CURRENCY_SAME": series["M1_YOY"].get(period),
                "FREE_CASH": series["M0"].get(period),
                "FREE_CASH_SAME": series["M0_YOY"].get(period),
            }
            for period in sorted(periods, reverse=True)
        ]

    def fetch_china_trade(self) -> list[dict[str, Any]]:
        current_year = market_today().year
        dts = f"{current_year - 2}01MM-{current_year}12MM"
        values_by_indicator = fetch_series_batch(
            _TRADE_CID,
            tuple(_TRADE_SERIES.values()),
            dts,
        )
        periods = set().union(*(values.keys() for values in values_by_indicator.values()))
        return [
            {
                "TIME": period,
                **{
                    field: values_by_indicator[indicator_id].get(period)
                    for field, indicator_id in _TRADE_SERIES.items()
                },
            }
            for period in sorted(periods, reverse=True)
        ]

    def fetch_china_industrial_production(self) -> list[dict[str, Any]]:
        return self._fetch_monthly_group("industrial_production")

    def fetch_china_retail_sales(self) -> list[dict[str, Any]]:
        return self._fetch_monthly_group("retail_sales")

    def fetch_china_fixed_asset_investment(self) -> list[dict[str, Any]]:
        return self._fetch_monthly_group("fixed_asset_investment")

    def fetch_china_real_estate(self) -> list[dict[str, Any]]:
        return self._fetch_monthly_group("real_estate")

    def fetch_china_employment(self) -> list[dict[str, Any]]:
        return self._fetch_monthly_group("employment")

    def fetch_china_social_financing(self, year: int | None = None) -> list[dict[str, Any]]:
        """Fetch monthly social-financing increments from the PBOC workbook."""
        index_html = _pbc_get_text(_PBC_INDEX_URL)
        year_links = re.findall(
            r'''href=["']([^"']+)["'][^>]*>\s*(\d{4})年统计数据\s*</a>''',
            index_html,
            flags=re.IGNORECASE,
        )
        if not year_links:
            raise PbocApiError("人民银行索引页未找到「XXXX年统计数据」链接，页面结构可能已变更")

        links_by_year = {int(year_text): href for href, year_text in year_links}
        target_year = max(links_by_year) if year is None else year
        if target_year not in links_by_year:
            available = sorted(links_by_year, reverse=True)[:8]
            raise ValueError(f"人民银行无 {target_year} 年数据，可选年份: {available}")

        year_url = urljoin(_PBC_INDEX_URL, links_by_year[target_year])
        year_html = _pbc_get_text(year_url)
        topic_links = re.findall(
            r'''href=["']([^"']+)["'][^>]*>\s*社会融资规模\s*</a>''',
            year_html,
            flags=re.IGNORECASE,
        )
        if not topic_links:
            raise PbocApiError(f"{target_year} 年页未找到「社会融资规模」专题链接")

        topic_url = urljoin(year_url, topic_links[0])
        topic_html = _pbc_get_text(topic_url)
        workbook_links = re.findall(
            r'''href=["']([^"']+\.xlsx?(?:\?[^"']*)?)["']''',
            topic_html,
            flags=re.IGNORECASE,
        )
        if not workbook_links:
            raise PbocApiError(f"{target_year} 年社融专题页未找到 xls/xlsx 附件")

        workbook_url = urljoin(topic_url, workbook_links[0])
        workbook_response = _pbc_get(workbook_url, timeout=_PBC_DOWNLOAD_TIMEOUT_SECONDS)
        raw = pd.read_excel(BytesIO(workbook_response.content), header=None)

        header_row = next(
            (
                index
                for index in range(len(raw))
                if str(raw.iloc[index, 0]).strip() == "月份"
            ),
            None,
        )
        if header_row is None:
            raise PbocApiError(
                f"{target_year} 年社融表没有独立的「月份」表头单元格；"
                "2020 及更早采用旧版式，本接口仅支持 2021 年起"
            )

        if raw.shape[1] < len(_PBC_SOCIAL_FINANCING_COLUMNS):
            raise PbocApiError(
                f"{target_year} 年社融表列数不足: "
                f"期望 {len(_PBC_SOCIAL_FINANCING_COLUMNS)} 列，实际 {raw.shape[1]} 列"
            )

        frame = raw.iloc[header_row + 3 :, : len(_PBC_SOCIAL_FINANCING_COLUMNS)].copy()
        frame.columns = _PBC_SOCIAL_FINANCING_COLUMNS
        frame["month"] = frame["month"].map(_pbc_month_label)
        frame = frame[frame["month"].notna()].copy()
        frame = frame[frame["month"].str.startswith(f"{target_year}-")].copy()
        for column in _PBC_SOCIAL_FINANCING_COLUMNS[1:]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame = frame.dropna(subset=["afre_total"])

        rows = [
            {
                "TIME": str(record.month),
                "SOCIAL_FINANCING_INCREMENT": _optional_float(record.afre_total),
                # Keep the existing macro contract as an alias for AkShare compatibility.
                "RMB_LOAN_ACCUMULATE": _optional_float(record.afre_total),
                "RMB_LOAN": _optional_float(record.rmb_loans),
                "FX_LOAN": _optional_float(record.fx_loans),
                "ENTRUSTED_LOAN": _optional_float(record.entrusted_loans),
                "TRUST_LOAN": _optional_float(record.trust_loans),
                "UNDISCOUNTED_BANKERS_ACCEPTANCE": _optional_float(
                    record.undiscounted_bankers_acceptance
                ),
                "CORPORATE_BOND": _optional_float(record.corporate_bonds),
                "GOVERNMENT_BOND": _optional_float(record.government_bonds),
                "EQUITY_FINANCING": _optional_float(record.equity_financing),
                "ABS_BY_DEPOSITORY": _optional_float(record.abs_by_depository),
                "LOANS_WRITTEN_OFF": _optional_float(record.loans_written_off),
            }
            for record in frame.itertuples(index=False)
        ]
        rows.sort(key=lambda row: row["TIME"], reverse=True)
        if not rows:
            raise PbocEmptyDataError(f"社融表解析后无有效月份（{target_year} 年），格式可能已变更")
        return rows

    def fetch_china_lpr(self) -> list[dict[str, Any]]:
        response = provider_get(
            _LPR_URL,
            params={"startDate": _LPR_START_DATE},
            headers=_SHIBOR_HEADERS,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if response.headers.get("Content-Type", "").lower().startswith("text/html"):
            raise NbsWafError("中国货币网返回 WAF HTML 页面")

        payload = response.json()
        head = payload.get("head") if isinstance(payload, Mapping) else None
        if not isinstance(head, Mapping) or str(head.get("rep_code")) != "200":
            message = head.get("rep_message") if isinstance(head, Mapping) else None
            raise ChinaMoneyApiError(f"中国货币网 LPR API 异常: {message or payload}")

        data = payload.get("data") if isinstance(payload, Mapping) else None
        columns = data.get("columns") if isinstance(data, Mapping) else None
        csv_text = data.get("csv") if isinstance(data, Mapping) else None
        if not isinstance(columns, list) or not isinstance(csv_text, str) or not csv_text.strip():
            raise ChinaMoneyEmptyDataError("中国货币网 LPR CSV 数据为空")

        column_indexes = {str(column).strip(): index for index, column in enumerate(columns)}
        required_columns = ("date", "1Y", "5Y")
        missing_columns = [column for column in required_columns if column not in column_indexes]
        if missing_columns:
            raise ChinaMoneyApiError(
                f"中国货币网 LPR CSV 缺少字段: {', '.join(missing_columns)}"
            )

        rows: list[dict[str, Any]] = []
        max_index = max(column_indexes[column] for column in required_columns)
        for values in csv.reader(StringIO(csv_text)):
            if not values or len(values) <= max_index:
                continue
            trade_date = values[column_indexes["date"]].strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", trade_date):
                continue
            try:
                datetime.strptime(trade_date, "%Y-%m-%d")
                lpr_1y = float(values[column_indexes["1Y"]].strip())
                raw_lpr_5y = values[column_indexes["5Y"]].strip()
                lpr_5y = float(raw_lpr_5y) if raw_lpr_5y else None
            except (ValueError, TypeError):
                continue
            if not math.isfinite(lpr_1y) or (
                lpr_5y is not None and not math.isfinite(lpr_5y)
            ):
                continue
            rows.append(
                {
                    "TIME": trade_date,
                    "TRADE_DATE": trade_date,
                    "LPR1Y": lpr_1y,
                    "LPR5Y": lpr_5y,
                }
            )

        rows.sort(key=lambda row: row["TIME"], reverse=True)
        if not rows:
            raise ChinaMoneyEmptyDataError("中国货币网 LPR 指标值为空")
        return rows

    def fetch_china_shibor(self) -> list[dict[str, Any]]:
        start_date, end_date = _shibor_history_window()
        timestamp = int(time.time() * 1000)
        response = provider_get(
            _SHIBOR_URL,
            params={
                "lang": "en",
                "startDate": _format_chinamoney_date(start_date),
                "endDate": _format_chinamoney_date(end_date),
                "t": timestamp,
                "_": timestamp,
            },
            headers=_SHIBOR_HEADERS,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        if response.headers.get("Content-Type", "").lower().startswith("text/html"):
            raise NbsWafError("中国货币网返回 WAF HTML 页面")

        payload = response.json()
        head = payload.get("head") if isinstance(payload, Mapping) else None
        if not isinstance(head, Mapping) or str(head.get("rep_code")) != "200":
            message = head.get("rep_message") if isinstance(head, Mapping) else None
            raise ChinaMoneyApiError(f"中国货币网 SHIBOR API 异常: {message or payload}")

        records = payload.get("records")
        if not isinstance(records, list):
            raise ChinaMoneyEmptyDataError("中国货币网 SHIBOR 历史记录为空")

        dated_records = [
            (str(record.get("showDateCN") or "")[:10], record)
            for record in records
            if isinstance(record, Mapping)
            and re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(record.get("showDateCN") or "")[:10])
        ]
        dated_records.sort(key=lambda item: item[0], reverse=True)
        if not dated_records:
            raise ChinaMoneyEmptyDataError("中国货币网 SHIBOR 历史日期为空")

        rows: list[dict[str, Any]] = []
        for record_index, (report_date, record) in enumerate(dated_records):
            previous_record = dated_records[record_index + 1][1] if record_index + 1 < len(dated_records) else None
            for source_field, period in _SHIBOR_TERMS:
                try:
                    rate = float(record[source_field])
                except (KeyError, TypeError, ValueError):
                    continue
                try:
                    previous_rate = float(previous_record[source_field]) if previous_record is not None else None
                except (KeyError, TypeError, ValueError):
                    previous_rate = None
                change_rate = round((rate - previous_rate) * 100, 10) if previous_rate is not None else None
                rows.append(
                    {
                        "REPORT_DATE": report_date,
                        "REPORT_PERIOD": period,
                        "IR_RATE": rate,
                        "CHANGE_RATE": change_rate,
                        "INDICATOR_ID": period,
                        "LATEST_RECORD": int(record_index == 0),
                        "MARKET": "上海银行间同业拆放利率",
                        "MARKET_CODE": "001",
                        "CURRENCY": "人民币",
                        "CURRENCY_CODE": "CNY",
                    }
                )
        if not rows:
            raise ChinaMoneyEmptyDataError("中国货币网 SHIBOR 指标值为空")
        return rows

    def fetch_china_gdp(self) -> list[dict[str, Any]]:
        nominal = self._load_series("GDP_NOMINAL_Q")
        index = self._load_series("GDP_INDEX_Q")
        return [
            {
                "TIME": period,
                "DOMESTICL_PRODUCT_BASE": nominal.get(period),
                "SUM_SAME": self._change_from_index(index.get(period)),
            }
            for period in sorted(set(nominal) | set(index), reverse=True)
        ]


nbs_provider = NbsDataProvider()

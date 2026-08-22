"""National Bureau of Statistics UUID-based macro-data provider."""

from __future__ import annotations

import os
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any, cast

import requests

from app.infrastructure.http.client import provider_post

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


class NbsEndpointError(ConnectionError):
    pass


class NbsWafError(ConnectionError):
    pass


class NbsApiError(RuntimeError):
    pass


class NbsEmptyDataError(ConnectionError):
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


def fetch_series(
    cid: str,
    indicator_id: str,
    dts: str,
    *,
    freq: str = "month",
) -> dict[str, float]:
    body = {
        "cid": cid,
        "indicatorIds": [indicator_id],
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
    if response.headers.get("Content-Type", "").lower().startswith("text/html"):
        raise NbsWafError("国家统计局返回 WAF HTML 页面")
    payload = response.json()
    if not isinstance(payload, Mapping) or payload.get("state") != 20000:
        message = payload.get("message") if isinstance(payload, Mapping) else None
        raise NbsApiError(f"国家统计局 API 异常: {message or payload}")
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise NbsEmptyDataError(f"国家统计局指标数据为空: cid={cid}, dts={dts}")
    result: dict[str, float] = {}
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
            result[period] = float(item["value"])
            break
    if not result:
        raise NbsEmptyDataError(f"国家统计局指标值为空: cid={cid}, dts={dts}")
    return result


class NbsDataProvider:
    name = "nbs"

    def _load_series(self, name: str) -> dict[str, float]:
        spec = cast(dict[str, Any], _SERIES[name])
        freq = str(spec["freq"])
        leaves = cast(tuple[tuple[str, str, int, int | None], ...], spec["leaves"])
        current_year = datetime.now().year
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

from datetime import datetime


from app.constants.http import CLS_HEADERS
from app.models.search_item import NewsSearchItem
from app.services.base.data_provider import BaseDataProvider
from app.utils import http_client
from app.utils.symbol_utils import contains_stock_reference


class ClsDataProvider(BaseDataProvider):
    def __init__(self):
        super().__init__(name="cls", source_label="财联社")

    def _fetch_telegraph(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        response = http_client.get("https://www.cls.cn/nodeapi/telegraphList", headers=CLS_HEADERS, timeout=10)
        items = response.json().get("data", {}).get("roll_data") or []

        results: list[NewsSearchItem] = []
        for item in items:
            title = str(item.get("title") or "").strip()
            content = str(item.get("content") or "").strip()
            url = str(item.get("shareurl") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            publish_time = self._parse_timestamp(item.get("ctime") or item.get("time") or item.get("created_at"))
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:200],
                    source="财联社",
                    publish_time=publish_time.strftime("%Y-%m-%d %H:%M:%S") if publish_time else "",
                    url=url,
                    author=item.get("author", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def _fetch_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        params = {
            "app": "CailianpressWeb",
            "os": "web",
            "sv": "8.4.6",
            "sign": "9f8797a1f4de66c2370f7a03990d2737",
        }
        response = http_client.get(
            "https://www.cls.cn/v3/depth/home/assembled/1000",
            params=params,
            headers=CLS_HEADERS,
            timeout=10,
        )
        data = http_client.parse_text_json(response).get("data", {}).get("depth_list", []) or []

        results: list[NewsSearchItem] = []
        for item in data:
            title = str(item.get("title") or "").strip()
            content = str(item.get("brief") or "").strip()
            combined = f"{title}\n{content}"
            if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                continue
            publish_time = self._parse_timestamp(item.get("ctime") or item.get("time") or item.get("created_at"))
            results.append(
                NewsSearchItem(
                    title=title,
                    content=content[:500],
                    source=item.get("source", ""),
                    publish_time=str(publish_time),
                    url=item.get("external_link", ""),
                    author=item.get("author", ""),
                    read_count=int(item.get("read_count", 0)),
                    comment_count=int(item.get("comment_count", 0)),
                )
            )
        return results

    def _parse_timestamp(self, value) -> datetime | None:
        if value in (None, "", 0, "0"):
            return None
        try:
            ts = int(float(value))
        except (TypeError, ValueError):
            return None
        if ts > 10**12:
            ts = ts / 1000
        try:
            return datetime.fromtimestamp(ts)
        except (OverflowError, OSError, ValueError):
            return None

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        news = self._fetch_news(code=code, code_name=code_name)
        telegraph = self._fetch_telegraph(code=code, code_name=code_name)
        return news + telegraph

cls_provider = ClsDataProvider()

if __name__ == "__main__":
    news = cls_provider.fetch_market_news()
    print(news)

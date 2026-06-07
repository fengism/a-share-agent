import logging


from app.constants.http import CLS_HEADERS
from app.models.search_item import NewsSearchItem
from app.services.base.data_provider import BaseDataProvider
from app.utils import http_client
from app.utils.symbol_utils import contains_stock_reference

logger = logging.getLogger(__name__)


class ClsDataProvider(BaseDataProvider):
    """Purpose: 封装财联社头条新闻接口，提供 A 股快讯数据获取。"""
    def __init__(self):
        """初始化 ClsDataProvider，固定 name 与 source_label。"""
        super().__init__(name="cls", source_label="财联社")

    def fetch_market_news(self, code: str = "", code_name: str = "") -> list[NewsSearchItem]:
        """财联社头条新闻。

        Param:
            code: 可选，6 位股票代码
            code_name: 可选，股票名称
        Return:
            财联社头条 NewsSearchItem 列表
        """
        try:
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

            data = http_client.parse_text_json(response).get("data", {})
            top_articles = data.get("top_article", []) or []
            articles = data.get("depth_list", []) or []
            articles = top_articles + articles
            results: list[NewsSearchItem] = []
            for item in articles:
                title = str(item.get("title") or "").strip()
                article_rec = item.get("article_rec", [])
                content = ""
                for rec in article_rec:
                    content += str(rec.get("brief") or "").strip()
                if content == "":
                   content = str(item.get("brief") or "").strip()
                if content == "":
                    continue
                combined = f"{title}\n{content}"
                if (code_name or code) and not contains_stock_reference(combined, code, code_name):
                    continue
                publish_time = self._parse_timestamp(item.get("ctime") or item.get("time") or item.get("created_at"))
                results.append(
                    NewsSearchItem(
                        title=title,
                        content=content[:500],
                        source=item.get("source", "财联社头条"),
                        publish_time=str(publish_time),
                        url=item.get("external_link", ""),
                        author=item.get("author", ""),
                        read_count=int(item.get("read_count", 0)),
                        comment_count=int(item.get("comment_count", 0)),
                    )
                )
            return results
        except Exception as e:
            logger.warning(f"财联社头条获取失败: {e}")
            return []

cls_provider = ClsDataProvider()

if __name__ == "__main__":
    news = cls_provider.fetch_market_news()
    print(news)

from app.models.search_item import NewsSearchItem


def fetch_guba_post(code: str = "600519", page: int = 1) -> list[NewsSearchItem]:
    """抓取东方财富股吧帖子列表。

    Param:
        code: 股票代码，默认 600519
        page: 页码，从 1 起
    Return:
        NewsSearchItem 列表
    """
    from app.services.providers.eastmoney import eastmoney_provider

    return eastmoney_provider.fetch_stock_guba_posts(code=code, page=page)

from app.models.search_item import NewsSearchItem


def fetch_guba_post(code: str = "600519", page: int = 1) -> list[NewsSearchItem]:
    from app.services.providers.eastmoney import eastmoney_provider

    return eastmoney_provider.fetch_stock_guba_posts(code=code, page=page)

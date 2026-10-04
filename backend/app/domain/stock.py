from pydantic import BaseModel


class StockConcept(BaseModel):
    """股票关联的行业或概念。"""

    code: str
    name: str


class StockConceptInfo(BaseModel):
    """股票的行业与概念集合。"""

    concepts: list[StockConcept]
    first_concept: StockConcept | None = None
    second_concept: StockConcept | None = None


class StockSearchItem(BaseModel):
    """股票搜索结果。"""

    code: str
    name: str
    price: float | None = None
    change_pct: float | None = None
    market: str = "cn"

"""东方财富数据提供者 — 按领域拆分的 Mixin 包。"""

from app.infrastructure.providers.eastmoney.base import EastMoneyBase
from app.infrastructure.providers.eastmoney.dragon_tiger import DragonTigerMixin
from app.infrastructure.providers.eastmoney.financials import FinancialsMixin
from app.infrastructure.providers.eastmoney.fund_flow import FundFlowMixin
from app.infrastructure.providers.eastmoney.industry import IndustryMixin
from app.infrastructure.providers.eastmoney.intraday import IntradayMixin
from app.infrastructure.providers.eastmoney.kline import KlineMixin
from app.infrastructure.providers.eastmoney.limit_pool import LimitPoolMixin
from app.infrastructure.providers.eastmoney.macro import MacroMixin
from app.infrastructure.providers.eastmoney.market import MarketMixin
from app.infrastructure.providers.eastmoney.misc import MiscMixin
from app.infrastructure.providers.eastmoney.news import NewsMixin
from app.infrastructure.providers.eastmoney.reports import ReportsMixin
from app.infrastructure.providers.eastmoney.search import SearchMixin


class EastMoneyDataProvider(
    EastMoneyBase,
    DragonTigerMixin,
    FinancialsMixin,
    FundFlowMixin,
    IndustryMixin,
    IntradayMixin,
    KlineMixin,
    LimitPoolMixin,
    MacroMixin,
    MarketMixin,
    MiscMixin,
    NewsMixin,
    ReportsMixin,
    SearchMixin,
):
    """东方财富数据提供者。多继承 Mixin，所有方法见各自子模块。"""


eastmoney_provider = EastMoneyDataProvider()
__all__ = ["EastMoneyDataProvider", "eastmoney_provider"]

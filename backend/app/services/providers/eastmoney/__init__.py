"""东方财富数据提供者 — 按领域拆分的 Mixin 包。"""

from app.services.providers.eastmoney.base import EastMoneyBase
from app.services.providers.eastmoney.dragon_tiger import DragonTigerMixin
from app.services.providers.eastmoney.financials import FinancialsMixin
from app.services.providers.eastmoney.fund_flow import FundFlowMixin
from app.services.providers.eastmoney.industry import IndustryMixin
from app.services.providers.eastmoney.intraday import IntradayMixin
from app.services.providers.eastmoney.kline import KlineMixin
from app.services.providers.eastmoney.limit_pool import LimitPoolMixin
from app.services.providers.eastmoney.macro import MacroMixin
from app.services.providers.eastmoney.market import MarketMixin
from app.services.providers.eastmoney.misc import MiscMixin
from app.services.providers.eastmoney.news import NewsMixin
from app.services.providers.eastmoney.reports import ReportsMixin
from app.services.providers.eastmoney.search import SearchMixin


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

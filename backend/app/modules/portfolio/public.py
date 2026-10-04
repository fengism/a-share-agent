"""Portfolio 模块对其他业务模块开放的稳定入口。"""

from app.modules.portfolio.positions import add_position, delete_position, list_held_stock_codes
from app.modules.portfolio.schemas import (
    PortfolioAccountSettings,
    PortfolioAccountSettingsUpdate,
    PortfolioEquityCurveResponse,
    PortfolioPosition,
    PortfolioPositionCreate,
    PortfolioResponse,
    PortfolioTransaction,
    PortfolioTransactionCreate,
    PortfolioTransactionPreview,
    is_hk_stock_code,
    normalize_portfolio_stock_code,
)
from app.modules.portfolio.service import get_equity_curve, get_portfolio, update_account_settings
from app.modules.portfolio.transactions import (
    InsufficientSharesError,
    PortfolioTransactionNotFoundError,
    UnknownPortfolioStockError,
    create_transaction,
    delete_transaction,
    preview_transaction,
    preview_transaction_update,
    update_transaction,
)

__all__ = [
    "InsufficientSharesError",
    "PortfolioAccountSettings",
    "PortfolioAccountSettingsUpdate",
    "PortfolioTransactionNotFoundError",
    "UnknownPortfolioStockError",
    "PortfolioEquityCurveResponse",
    "PortfolioPosition",
    "PortfolioPositionCreate",
    "PortfolioResponse",
    "PortfolioTransaction",
    "PortfolioTransactionCreate",
    "PortfolioTransactionPreview",
    "add_position",
    "create_transaction",
    "delete_position",
    "delete_transaction",
    "get_equity_curve",
    "get_portfolio",
    "list_held_stock_codes",
    "preview_transaction",
    "preview_transaction_update",
    "is_hk_stock_code",
    "normalize_portfolio_stock_code",
    "update_transaction",
    "update_account_settings",
]

"""Hong Kong market data backed by Sina Finance."""

from app.financial_data.hk.service import HKMarketService, hk_market_service

__all__ = ["HKMarketService", "hk_market_service"]

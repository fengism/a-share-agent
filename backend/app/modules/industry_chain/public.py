"""Industry Chain 模块对其他业务模块开放的稳定入口。"""

from app.modules.industry_chain.collector import (
    IndustryChainDataUnavailableError,
    collect_industry_chain_data,
)
from app.modules.industry_chain.persistence.repository import load_industry_chain
from app.modules.industry_chain.research import research_industry_chain

__all__ = [
    "collect_industry_chain_data",
    "IndustryChainDataUnavailableError",
    "load_industry_chain",
    "research_industry_chain",
]

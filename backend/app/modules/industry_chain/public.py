"""Industry Chain 模块对其他业务模块开放的稳定入口。"""

from app.domain.industry_chain import resolve_industry_chain_scope
from app.modules.industry_chain.archive_service import (
    get_latest_industry_chain_archive,
    list_industry_chain_history,
    load_industry_chain,
    load_industry_chain_archive,
    remove_industry_chain_archive,
)
from app.modules.industry_chain.collector import (
    IndustryChainDataUnavailableError,
    collect_industry_chain_data,
)
from app.modules.industry_chain.pdf_service import (
    generate_industry_chain_pdf_html,
    render_industry_chain_pdf_bytes,
)
from app.modules.industry_chain.pipeline import run_industry_chain_analysis
from app.modules.industry_chain.research import research_industry_chain
from app.modules.industry_chain.schemas import (
    IndustryChainHistoryItem,
    IndustryChainLatestResponse,
    IndustryChainResearchScope,
    IndustryChainResult,
)
from app.modules.industry_chain.stream import create_industry_chain_event_generator
from app.modules.workflow.public import WorkflowCapacityError

__all__ = [
    "IndustryChainDataUnavailableError",
    "IndustryChainHistoryItem",
    "IndustryChainLatestResponse",
    "IndustryChainResult",
    "IndustryChainResearchScope",
    "WorkflowCapacityError",
    "collect_industry_chain_data",
    "create_industry_chain_event_generator",
    "generate_industry_chain_pdf_html",
    "get_latest_industry_chain_archive",
    "list_industry_chain_history",
    "load_industry_chain",
    "load_industry_chain_archive",
    "remove_industry_chain_archive",
    "render_industry_chain_pdf_bytes",
    "research_industry_chain",
    "resolve_industry_chain_scope",
    "run_industry_chain_analysis",
]

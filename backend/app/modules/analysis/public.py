"""Analysis 模块对 HTTP 和其他业务适配器开放的稳定入口。"""

from app.modules.analysis.history_service import (
    get_analysis_by_date,
    get_latest_analysis,
    list_all_analysis_history,
    list_analysis_history,
    load_analysis_history,
    load_latest_analysis,
    remove_analysis_history,
)
from app.modules.analysis.models import AnalysisResult, FactorAnalysis
from app.modules.analysis.page_service import get_analysis_page_data
from app.modules.analysis.pdf_service import (
    generate_research_report_html,
    render_pdf_bytes_from_html,
)
from app.modules.analysis.pipeline import run_analysis
from app.modules.analysis.schemas import AnalysisHistoryItem, AnalysisPageData
from app.modules.analysis.stream import create_analysis_event_generator
from app.modules.workflow.public import WorkflowCapacityError

__all__ = [
    "AnalysisHistoryItem",
    "AnalysisPageData",
    "AnalysisResult",
    "FactorAnalysis",
    "WorkflowCapacityError",
    "create_analysis_event_generator",
    "generate_research_report_html",
    "get_analysis_page_data",
    "get_latest_analysis",
    "get_analysis_by_date",
    "list_all_analysis_history",
    "list_analysis_history",
    "load_analysis_history",
    "load_latest_analysis",
    "remove_analysis_history",
    "render_pdf_bytes_from_html",
    "run_analysis",
]

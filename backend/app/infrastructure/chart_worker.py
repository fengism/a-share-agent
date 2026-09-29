"""One-shot PNG worker. No data acquisition or external message delivery here."""

from __future__ import annotations

import base64
import json
import sys


def render(request: dict) -> list[tuple[str, bytes]]:
    kind = request["kind"]
    if kind == "analysis":
        from app.domain.market import KlineData
        from app.modules.analysis.chart_images import render_analysis_chart_pngs
        from app.modules.analysis.models import AnalysisResult

        kline = KlineData.model_validate(request["kline"]) if request.get("kline") else None
        return list(render_analysis_chart_pngs(AnalysisResult.model_validate(request["data"]), kline))
    if kind == "daily_review":
        from app.modules.daily_review.chart_images import render_daily_review_chart_pngs
        from app.modules.daily_review.models import DailyReviewDataSnapshot

        return list(render_daily_review_chart_pngs(DailyReviewDataSnapshot.model_validate(request["data"])))
    if kind == "industry_chain":
        from app.modules.industry_chain.chart_images import render_industry_chain_chart_pngs
        from app.modules.industry_chain.models import IndustryChainResult

        return list(render_industry_chain_chart_pngs(IndustryChainResult.model_validate(request["data"])))
    raise ValueError("unsupported chart kind")


if __name__ == "__main__":
    payload = json.loads(sys.stdin.buffer.read(8 * 1024 * 1024 + 1))
    images = render(payload)
    sys.stdout.write(json.dumps([(title, base64.b64encode(png).decode("ascii")) for title, png in images]))

"""从 AI 产业链分析结果自动挖掘知识库条目。

把 IndustryChainResult 的上/中/下游节点（含代表公司与代码）转换为
AtlasChain，公司名通过本地股票名称表反查代码，写入导入目录并立即生效。
同名链的挖掘结果按 slug 稳定覆盖（auto-<name-hash>）。
"""

from __future__ import annotations

import hashlib
import logging

from app.configuration import get_settings
from app.core.market import is_a_share_code
from app.financial_data.stock.profile.name_map import get_stock_name_map
from app.modules.industry_chain.atlas.contracts import AtlasChain
from app.modules.industry_chain.atlas.loader import (
    _import_dir,
    _registry,
    _write_chain_file,
)
from app.modules.industry_chain.models import IndustryChainResult

logger = logging.getLogger(__name__)

# 低于该规模的分析结果不挖掘，避免低质量条目污染知识库
_MIN_SEGMENTS = 2
_MIN_COMPANIES = 3
_SUMMARY_LIMIT = 120


def mining_slug(name: str) -> str:
    digest = hashlib.sha1(name.strip().encode("utf-8")).hexdigest()[:10]
    return f"auto-{digest}"


def _build_name_to_code(code_to_name: dict[str, str]) -> dict[str, str]:
    name_to_code: dict[str, str] = {}
    for code, name in code_to_name.items():
        name_to_code.setdefault(name, code)
    return name_to_code


def _resolve_companies(
    result_node, name_to_code: dict[str, str], code_to_name: dict[str, str],
) -> list[dict]:
    """解析节点代表公司；代码与公司名必须能对上名称表，防止幻觉配对污染知识库。"""
    companies: dict[str, dict] = {}
    code = str(result_node.code or "").strip()
    company = (result_node.company or "").strip()
    if company and is_a_share_code(code):
        if name_to_code.get(company) == code:
            companies[code] = {
                "name": company,
                "code": code,
                "note": (result_node.role or "")[:40],
            }
        # 代码与公司名对不上时丢弃该配对
    elif not company and is_a_share_code(code) and code in code_to_name:
        # 仅给出代码时，用名称表反查公司名
        companies[code] = {
            "name": code_to_name[code],
            "code": code,
            "note": (result_node.role or "")[:40],
        }
    for name in result_node.companies or []:
        normalized = (name or "").strip()
        if not normalized:
            continue
        resolved = name_to_code.get(normalized)
        if resolved and resolved not in companies:
            companies[resolved] = {"name": normalized, "code": resolved, "note": ""}
    return list(companies.values())


async def build_mined_chain(result: IndustryChainResult) -> AtlasChain | None:
    """把分析结果转换为 AtlasChain；可挖掘内容不足时返回 None。"""
    name = (result.name or "").strip()
    if not name:
        return None
    code_map = await get_stock_name_map()
    name_to_code = _build_name_to_code(code_map)

    layers: list[dict] = []
    total_companies = 0
    for key, label, nodes in (
        ("upstream", "上游", result.upstream),
        ("midstream", "中游", result.midstream),
        ("downstream", "下游", result.downstream),
    ):
        segments: list[dict] = []
        for node in nodes:
            companies = _resolve_companies(node, name_to_code, code_map)
            if not companies:
                continue
            segment_name = (node.name or node.role or node.company or "").strip()
            segments.append({
                "name": segment_name or "未命名环节",
                "companies": companies,
            })
            total_companies += len(companies)
        if segments:
            layers.append({
                "key": key,
                "name": f"{label} · AI 挖掘",
                "segments": segments,
            })

    total_segments = sum(len(layer["segments"]) for layer in layers)
    if total_segments < _MIN_SEGMENTS or total_companies < _MIN_COMPANIES:
        logger.info(
            "产业链挖掘跳过（内容不足）: name=%s, segments=%s, companies=%s",
            name, total_segments, total_companies,
        )
        return None

    raw_summary = (result.summary or result.positioning or "").strip()
    if not raw_summary:
        raw_summary = f"由 AI 产业链分析自动挖掘的{name}产业链结构。"
    summary = raw_summary[: _SUMMARY_LIMIT - 1] + "…" if len(raw_summary) > _SUMMARY_LIMIT else raw_summary

    return AtlasChain.model_validate({
        "slug": mining_slug(name),
        "name": name,
        "category": "AI 挖掘",
        "summary": summary,
        "aliases": (result.aliases or [])[:5],
        "tags": ["AI挖掘"],
        "drivers": (result.drivers or [])[:3],
        "layers": layers,
        "mined": True,
    })


def save_mined_chain(chain: AtlasChain) -> None:
    """挖掘结果直接覆盖同 slug 的历史挖掘文件并立即生效。"""
    import_dir = _import_dir()
    import_dir.mkdir(parents=True, exist_ok=True)
    _write_chain_file(import_dir, chain)
    _registry.force_refresh()


async def mine_and_save_atlas_chain(result: IndustryChainResult) -> AtlasChain | None:
    """挖掘并落盘；由自动与手动入口共用，失败只影响本次挖掘。"""
    chain = await build_mined_chain(result)
    if chain is None:
        return None
    save_mined_chain(chain)
    logger.info("产业链知识库挖掘入库: name=%s, slug=%s", chain.name, chain.slug)
    # 返回重载后的条目，让 source 反映 mined 映射
    state = _registry.current()
    return state.chains.get(chain.slug, chain)


async def auto_mine_from_result(result: IndustryChainResult) -> None:
    """分析完成后的自动挖掘钩子；失败只记日志，不影响分析结果。"""
    if not get_settings().industry_atlas_auto_mining:
        return
    try:
        await mine_and_save_atlas_chain(result)
    except Exception:
        logger.warning(
            "产业链知识库自动挖掘失败: name=%s", result.name, exc_info=True,
        )

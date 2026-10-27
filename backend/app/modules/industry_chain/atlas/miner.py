"""从 AI 产业链分析结果自动挖掘知识库条目。

把 IndustryChainResult 的上/中/下游节点（含代表公司与代码）转换为
AtlasChain，公司名通过本地股票名称表反查代码，写入导入目录并立即生效。
同名链的挖掘结果按 slug 稳定覆盖（auto-<name-hash>）。
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field

from app.configuration import get_settings
from app.core.market import is_a_share_code, is_hk_code
from app.domain.timezones import market_now
from app.financial_data.stock.profile.name_map import get_stock_name_map
from app.modules.industry_chain.atlas.contracts import AtlasChain
from app.modules.industry_chain.atlas.loader import (
    _import_dir,
    _registry,
    _user_atlas_dir,
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


_COMPANY_CLEAN_RE = re.compile(
    r"(?:股份有限公司|有限责任公司|有限公司|（集团）有限公司|集团有限公司|集团股份公司|股份公司|集团|科技)+$"
)


def _normalize_name(name: str) -> str:
    cleaned = re.sub(r"[\(\)（）\s]", "", name)
    return _COMPANY_CLEAN_RE.sub("", cleaned).strip()


def _build_name_to_code(code_to_name: dict[str, str]) -> tuple[dict[str, str], dict[str, str]]:
    name_to_code: dict[str, str] = {}
    clean_name_to_code: dict[str, str] = {}
    for code, name in code_to_name.items():
        name_to_code.setdefault(name, code)
        norm = _normalize_name(name)
        if norm and len(norm) >= 2:
            clean_name_to_code.setdefault(norm, code)
    return name_to_code, clean_name_to_code


def _match_code(name: str, name_to_code: dict[str, str], clean_name_to_code: dict[str, str]) -> str:
    if name in name_to_code:
        return name_to_code[name]
    norm = _normalize_name(name)
    if norm in clean_name_to_code:
        return clean_name_to_code[norm]
    return ""


def _is_supported_market_code(code: str) -> bool:
    return is_a_share_code(code) or is_hk_code(code)


def _resolve_companies(
    result_node,
    name_to_code: dict[str, str],
    clean_name_to_code: dict[str, str],
    code_to_name: dict[str, str],
    key_stocks_notes: dict[str, str] | None = None,
) -> list[dict]:
    """解析节点代表公司；支持A股与港股标的，并兼容简称归一化匹配。"""
    companies: dict[str, dict] = {}
    key_notes = key_stocks_notes or {}
    code = str(result_node.code or "").strip()
    company = (result_node.company or "").strip()
    if company and _is_supported_market_code(code):
        matched_code = _match_code(company, name_to_code, clean_name_to_code)
        if matched_code == code or is_hk_code(code) or (not matched_code and code in code_to_name):
            display_name = code_to_name.get(code) or company
            custom_note = key_notes.get(code) or (result_node.role or "")
            companies[code] = {
                "name": display_name,
                "code": code,
                "note": custom_note[:50],
            }
    elif not company and _is_supported_market_code(code) and code in code_to_name:
        # 仅给出代码时，用名称表反查公司名
        custom_note = key_notes.get(code) or (result_node.role or "")
        companies[code] = {
            "name": code_to_name[code],
            "code": code,
            "note": custom_note[:50],
        }
    for name in result_node.companies or []:
        normalized = (name or "").strip()
        if not normalized:
            continue
        resolved = _match_code(normalized, name_to_code, clean_name_to_code)
        if resolved and resolved not in companies:
            display_name = code_to_name.get(resolved) or normalized
            custom_note = key_notes.get(resolved) or ""
            companies[resolved] = {"name": display_name, "code": resolved, "note": custom_note[:50]}
    return list(companies.values())


async def build_mined_chain(
    result: IndustryChainResult,
    user_id: int | None = None,
) -> AtlasChain | None:
    """把分析结果转换为 AtlasChain；可挖掘内容不足时返回 None。"""
    name = (result.name or "").strip()
    if not name:
        return None
    code_map = await get_stock_name_map()
    name_to_code, clean_name_to_code = _build_name_to_code(code_map)

    # 提炼重点标的的核心受益逻辑、壁垒及出海敞口，注入到图谱标的 Note
    key_notes: dict[str, str] = {}
    for ks in getattr(result, "key_stocks", []) or []:
        ks_code = str(getattr(ks, "code", "") or "").strip()
        ks_parts = []
        core_desc = getattr(ks, "benefit_path", "") or getattr(ks, "moat", "") or getattr(ks, "role", "")
        if core_desc:
            ks_parts.append(core_desc)
        if getattr(ks, "overseas_share", ""):
            ks_parts.append(f"出海: {ks.overseas_share}")
        if ks_code and ks_parts:
            key_notes[ks_code] = " ｜ ".join(ks_parts)

    # 建立环节到价值量与毛利率的映射
    bom_map: dict[str, str] = {}
    for vd in getattr(result, "value_distribution", []) or []:
        seg_k = (getattr(vd, "segment", "") or "").strip().lower()
        if seg_k:
            details = []
            if getattr(vd, "cost_share", ""):
                details.append(f"BOM: {vd.cost_share}")
            if getattr(vd, "gross_margin_range", ""):
                details.append(f"毛利: {vd.gross_margin_range}")
            if details:
                bom_map[seg_k] = " · ".join(details)

    layers: list[dict] = []
    total_companies = 0
    for key, label, nodes in (
        ("upstream", "上游", result.upstream),
        ("midstream", "中游", result.midstream),
        ("downstream", "下游", result.downstream),
    ):
        segments: list[dict] = []
        for node in nodes:
            companies = _resolve_companies(node, name_to_code, clean_name_to_code, code_map, key_notes)
            if not companies:
                continue
            segment_name = (node.name or node.role or node.company or "").strip()
            desc_parts = [p for p in (node.role, node.description, node.market_share or node.metric) if p]
            bom_info = bom_map.get(segment_name.lower())
            if bom_info:
                desc_parts.append(bom_info)
            segment_desc = "；".join(desc_parts) if desc_parts else ""
            segments.append(
                {
                    "name": segment_name or "未命名环节",
                    "description": segment_desc[:120],
                    "companies": companies,
                }
            )
            total_companies += len(companies)
        if segments:
            layers.append(
                {
                    "key": key,
                    "name": f"{label} · AI 挖掘",
                    "segments": segments,
                }
            )

    total_segments = sum(len(layer["segments"]) for layer in layers)
    if total_segments < _MIN_SEGMENTS or total_companies < _MIN_COMPANIES:
        logger.info(
            "产业链挖掘跳过（内容不足）: name=%s, segments=%s, companies=%s",
            name,
            total_segments,
            total_companies,
        )
        return None

    raw_summary = (result.summary or result.positioning or "").strip()
    if not raw_summary:
        raw_summary = f"由 AI 产业链分析自动挖掘的{name}产业链结构。"
    summary = raw_summary[: _SUMMARY_LIMIT - 1] + "…" if len(raw_summary) > _SUMMARY_LIMIT else raw_summary

    category = "个人专属" if user_id is not None else "AI 挖掘"
    tags = ["个人专属"] if user_id is not None else ["AI挖掘"]
    source = "user" if user_id is not None else "mined"
    slug = f"user-{mining_slug(name)[5:]}" if user_id is not None else mining_slug(name)

    return AtlasChain.model_validate(
        {
            "slug": slug,
            "name": name,
            "category": category,
            "summary": summary,
            "aliases": (result.aliases or [])[:5],
            "tags": tags,
            "drivers": (result.drivers or [])[:3],
            "layers": layers,
            "source": source,
            "mined": True,
            "mined_at": market_now().isoformat(timespec="seconds"),
            "archive_id": result.archive_id or "",
        }
    )


def save_mined_chain(chain: AtlasChain, user_id: int | None = None) -> None:
    """挖掘结果直接覆盖同 slug 的历史挖掘文件并立即生效。"""
    target_dir = _user_atlas_dir(user_id) if user_id is not None else _import_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    _write_chain_file(target_dir, chain)
    _registry.force_refresh()


async def mine_and_save_atlas_chain(
    result: IndustryChainResult,
    user_id: int | None = None,
) -> AtlasChain | None:
    """挖掘并落盘；由自动与手动入口共用，失败只影响本次挖掘。"""
    chain = await build_mined_chain(result, user_id=user_id)
    if chain is None:
        return None
    save_mined_chain(chain, user_id=user_id)
    logger.info(
        "产业链知识库挖掘入库: name=%s, slug=%s, user_id=%s",
        chain.name,
        chain.slug,
        user_id,
    )
    if user_id is not None:
        return chain.model_copy(update={"source": "user"})
    state = _registry.current()
    return state.chains.get(chain.slug, chain)


async def auto_mine_from_result(
    result: IndustryChainResult,
    user_id: int | None = None,
) -> None:
    """分析完成后的自动挖掘钩子；失败只记日志，不影响分析结果。"""
    if not get_settings().industry_atlas_auto_mining:
        return
    try:
        await mine_and_save_atlas_chain(result, user_id=user_id)
    except Exception:
        logger.warning(
            "产业链知识库自动挖掘失败: name=%s, user_id=%s",
            result.name,
            user_id,
            exc_info=True,
        )


class AtlasBatchMineItem(BaseModel):
    """批量挖掘的单条结果。action=created 新建条目，merged 覆盖同 slug 旧条目。"""

    name: str
    slug: str
    action: Literal["created", "merged"]
    company_count: int = 0
    segment_count: int = 0


class AtlasBatchMineResponse(BaseModel):
    """批量挖掘汇总；scanned 为扫描存档数，skipped 为未通过质量门或内容不足的存档数。"""

    scanned: int = 0
    succeeded: int = 0
    skipped: int = 0
    chains: list[AtlasBatchMineItem] = Field(default_factory=list)


async def batch_mine_atlas_chains(
    results: list[tuple[str, IndustryChainResult]],
) -> AtlasBatchMineResponse:
    """批量挖掘多条存档；单条失败只跳过，不影响其余条目。"""
    existing_slugs = set(_registry.current().chains)
    response = AtlasBatchMineResponse(scanned=len(results))
    for name, result in results:
        try:
            slug = mining_slug(result.name or name)
            action: Literal["created", "merged"] = "merged" if slug in existing_slugs else "created"
            chain = await mine_and_save_atlas_chain(result)
        except Exception:
            logger.warning("产业链知识库批量挖掘失败: name=%s", name, exc_info=True)
            response.skipped += 1
            continue
        if chain is None:
            response.skipped += 1
            continue
        existing_slugs.add(chain.slug)
        response.succeeded += 1
        response.chains.append(
            AtlasBatchMineItem(
                name=chain.name,
                slug=chain.slug,
                action=action,
                company_count=chain.company_count,
                segment_count=chain.segment_count,
            )
        )
    return response

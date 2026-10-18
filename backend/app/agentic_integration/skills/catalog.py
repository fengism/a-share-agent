from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.skills.contracts import Skill
from app.agentic_integration.skills.loader import load_builtin_skills
from app.agentic_integration.skills.packs.industry import SKILLS as INDUSTRY_SKILLS
from app.agentic_integration.skills.packs.market import SKILLS as MARKET_SKILLS
from app.agentic_integration.skills.packs.quant import SKILLS as QUANT_SKILLS
from app.agentic_integration.skills.packs.stock import SKILLS as STOCK_SKILLS
from app.agentic_integration.skills.packs.web import SKILLS as WEB_SKILLS

SKILL_PACKS = (
    WEB_SKILLS,
    STOCK_SKILLS,
    INDUSTRY_SKILLS,
    MARKET_SKILLS,
    QUANT_SKILLS,
)


def list_python_skills() -> list[Skill]:
    """Legacy Python-pack source kept for Phase 1 parity and rollback."""
    return sorted(
        (skill for pack in SKILL_PACKS for skill in pack),
        key=lambda skill: (skill.priority, skill.name),
    )


def list_builtin_skills() -> list[Skill]:
    """Load the file-based definitions; Python packs remain as a parity oracle."""
    return load_builtin_skills()


def register_skill_catalog(target_catalog: CapabilityCatalog = registry) -> None:
    before = target_catalog.skill_names()
    try:
        for skill in list_builtin_skills():
            target_catalog.register_skill(skill)
        target_catalog.validate_skill_coverage()
    except Exception:
        target_catalog.unregister_skills(target_catalog.skill_names() - before)
        raise

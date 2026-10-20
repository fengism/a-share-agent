from app.agentic.catalog import CapabilityCatalog, registry
from app.agentic.skills.contracts import Skill
from app.agentic_integration.skills.loader import load_builtin_skills


def list_builtin_skills() -> list[Skill]:
    """Load the file-based definitions; ``SKILL.md`` is the only source."""
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

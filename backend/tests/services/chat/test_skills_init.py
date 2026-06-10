from app.services.chat import skills


def test_register_all_skills_is_idempotent(monkeypatch):
    """register_all_skills should only invoke concrete registrars once."""
    calls: list[str] = []

    monkeypatch.setattr(skills, "_skills_registered", False)
    monkeypatch.setattr(skills, "register_all_tools", lambda: calls.append("tools"))
    monkeypatch.setattr(skills, "register_skill_catalog", lambda: calls.append("catalog"))

    skills.register_all_skills()
    skills.register_all_skills()

    assert calls == ["tools", "catalog"]

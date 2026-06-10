from app.services.chat import skills


def test_register_all_skills_is_idempotent(monkeypatch):
    """register_all_skills should only invoke concrete registrars once."""
    calls: list[str] = []

    monkeypatch.setattr(skills, "_skills_registered", False)
    monkeypatch.setattr(skills, "register_stock_skills", lambda: calls.append("stock"))
    monkeypatch.setattr(skills, "register_market_skills", lambda: calls.append("market"))
    monkeypatch.setattr(skills, "register_composite_skills", lambda: calls.append("composite"))
    monkeypatch.setattr(skills, "register_web_skills", lambda: calls.append("web"))

    skills.register_all_skills()
    skills.register_all_skills()

    assert calls == ["stock", "market", "composite", "web"]

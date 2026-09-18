from pathlib import Path
import pytest


def test_real_nanobot_skill_loader():
    pytest.importorskip("nanobot")
    from nanobot.agent.skills import SkillsLoader
    root = Path(__file__).resolve().parents[1]
    loader = SkillsLoader(root)
    assert any(s["name"] == "ai-model-router" for s in loader.list_skills())
    assert "--json-stdin" in loader.load_skill("ai-model-router")
    assert "ai-model-router" in loader.build_skills_summary()

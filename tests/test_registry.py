import pytest
from fsb.skills.registry import get_builtin_skills
from fsb.workflows.registry import get_builtin_workflows


def test_get_builtin_skills_returns_list():
    skills = get_builtin_skills()
    assert isinstance(skills, list)
    assert len(skills) >= 1
    assert all(s.skillId for s in skills)
    assert all(s.name for s in skills)
    assert all(hasattr(s, "type") for s in skills)


def test_get_builtin_skills_first_entry():
    skills = get_builtin_skills()
    first = skills[0]
    assert first.skillId == "cash-flow-snapshot"
    assert first.displayName == "现金流快照"


def test_get_builtin_skills_last_entry():
    skills = get_builtin_skills()
    last = skills[-1]
    assert last.skillId == "kpi-dashboard-data"


def test_get_builtin_workflows_returns_list():
    workflows = get_builtin_workflows()
    assert isinstance(workflows, list)
    assert len(workflows) >= 1
    assert all(w.name for w in workflows)


def test_get_builtin_workflows_first_entry():
    workflows = get_builtin_workflows()
    first = workflows[0]
    assert first.name == "invoice-chase"
    assert first.slashCommand == "/invoice-chase"


def test_get_builtin_workflows_have_graph():
    workflows = get_builtin_workflows()
    for w in workflows:
        assert w.graphDefinition is not None
        assert w.graphDefinition.entryNode is not None
        assert len(w.graphDefinition.nodes) > 0

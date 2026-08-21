import pytest

from labhive.models.lab_membership import CompensationType, LabRole, MANAGER_ROLES


def test_lab_role_has_eight_values():
    assert len(LabRole) == 9


def test_lab_role_values():
    values = {r.value for r in LabRole}
    assert values == {
        "lab_coordinator",
        "engineering_manager",
        "project_manager",
        "chief_scientist",
        "tech_lead",
        "engineer",
        "researcher",
        "research_fellow",
        "staff",
    }


def test_lab_role_from_string():
    assert LabRole("engineering_manager") == LabRole.engineering_manager
    assert LabRole("staff") == LabRole.staff


def test_lab_role_invalid_raises():
    with pytest.raises(ValueError):
        LabRole("superstar")


def test_manager_roles_constant():
    assert LabRole.lab_coordinator in MANAGER_ROLES
    assert LabRole.engineering_manager in MANAGER_ROLES
    assert LabRole.project_manager in MANAGER_ROLES
    assert LabRole.chief_scientist in MANAGER_ROLES
    assert LabRole.engineer not in MANAGER_ROLES
    assert LabRole.staff not in MANAGER_ROLES


def test_compensation_type_values():
    values = {c.value for c in CompensationType}
    assert values == {"project_salary", "research_grant", "volunteer"}


def test_compensation_type_from_string():
    assert CompensationType("project_salary") == CompensationType.project_salary
    assert CompensationType("research_grant") == CompensationType.research_grant

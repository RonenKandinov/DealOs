"""Relation records stay on the macro side of the graph."""

from dealos.macro_world.relations.models import (
    BRIDGE,
    MACRO_R0,
    RELATION_ENDS,
    VOCABULARY,
    RelationMutation,
    macro_r0,
)
from dealos.macro_world.relations.validate import mutation_errors


def test_the_baseline_is_only_the_phase1_resource_identity_pair() -> None:
    assert macro_r0().primitives == MACRO_R0
    assert "Role" not in macro_r0().primitives
    assert "ResourceRoleAssociation" in VOCABULARY


def test_relation_endpoints_are_macro_entities() -> None:
    for source, target in RELATION_ENDS.values():
        assert source not in BRIDGE
        assert target not in BRIDGE
        assert "Task" not in source and "Task" not in target
        assert "Deal" not in source and "Deal" not in target


def test_a_micro_bridge_target_is_rejected() -> None:
    assert mutation_errors(RelationMutation("AddRelation", "TaskOccurrence"))
    assert mutation_errors(RelationMutation("AddRelation", "Deal"))
    assert mutation_errors(RelationMutation("RewriteCode", "Role"))
    assert mutation_errors(RelationMutation("AddRelation", "reports_to"))
    assert mutation_errors(RelationMutation("AddRelation", "ResourceRoleAssociation")) == ()

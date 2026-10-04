"""The MVP mutation grammar. Each operator adds one named component."""

from __future__ import annotations

from dealos.problem_evolution.models import Component, Mutation

ADD_OCCURRENCE = "AddOccurrence"
ADD_LIFECYCLE = "AddLifecycle"
ADD_OBJECT = "AddObject"
ADD_RELATION = "AddRelation"
ADD_STATE = "AddState"
SPLIT_OBJECT = "SplitObject"

OPERATORS = frozenset(
    {ADD_OCCURRENCE, ADD_LIFECYCLE, ADD_OBJECT, ADD_RELATION, ADD_STATE, SPLIT_OBJECT}
)

# Names already implemented on the simulator. The mutation only records that a
# candidate representation includes them.
OCCURRENCE = Component("TaskOccurrence", "execution")
LIFECYCLE = Component("Lifecycle", "lifecycle")
OFFER_IDENTITY = Component("OfferIdentity", "object_identity")


def add_occurrence() -> Mutation:
    return Mutation(ADD_OCCURRENCE, "execution", OCCURRENCE)


def add_lifecycle() -> Mutation:
    return Mutation(ADD_LIFECYCLE, "lifecycle", LIFECYCLE)


def add_object(name: str = "OfferIdentity") -> Mutation:
    component = OFFER_IDENTITY if name == "OfferIdentity" else Component(name, "object_identity")
    return Mutation(ADD_OBJECT, "object_identity", component)

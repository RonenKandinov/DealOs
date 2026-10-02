import pytest

from dealos.domain.graph import CycleError, descendants, has_cycle, predecessors, successors
from dealos.domain.models import DealGraph, Task


def _task(deal_id: str, name: str) -> Task:
    return Task(task_id=f"{deal_id}:{name}", deal_id=deal_id, task_type="commercial", name=name)


def _graph(names: list[str], edges: list[tuple[str, str]], targets: list[str] | None = None) -> DealGraph:
    deal_id = "deal_00"
    tasks = {f"{deal_id}:{name}": _task(deal_id, name) for name in names}
    full_edges = frozenset((f"{deal_id}:{src}", f"{deal_id}:{dst}") for src, dst in edges)
    if targets is None:
        targets = [name for name in names if not any(src == name for src, _dst in edges)]
    return DealGraph(
        deal_id=deal_id,
        tasks=tasks,
        edges=full_edges,
        targets=frozenset(f"{deal_id}:{name}" for name in targets),
    )


def test_task_with_no_predecessors() -> None:
    graph = _graph(["only"], [])
    assert predecessors(graph.edges, "deal_00:only") == ()
    assert successors(graph.edges, "deal_00:only") == ()


def test_multiple_predecessors_and_merge() -> None:
    graph = _graph(
        ["left", "right", "join", "close"],
        [("left", "join"), ("right", "join"), ("join", "close")],
    )
    assert predecessors(graph.edges, "deal_00:join") == ("deal_00:left", "deal_00:right")
    assert descendants(graph.edges, "deal_00:left") == frozenset({"deal_00:join", "deal_00:close"})
    assert descendants(graph.edges, "deal_00:right") == frozenset({"deal_00:join", "deal_00:close"})
    assert descendants(graph.edges, "deal_00:close") == frozenset()


def test_single_task_deal_is_its_own_target() -> None:
    graph = _graph(["only"], [])
    assert graph.targets == frozenset({"deal_00:only"})


def test_cycle_is_rejected() -> None:
    with pytest.raises(CycleError):
        _graph(["a", "b"], [("a", "b"), ("b", "a")], targets=["a"])


def test_self_loop_is_rejected() -> None:
    with pytest.raises(CycleError):
        _graph(["a"], [("a", "a")], targets=["a"])


def test_has_cycle_on_raw_edges() -> None:
    assert has_cycle({"a", "b"}, {("a", "b"), ("b", "a")})
    assert not has_cycle({"a"}, set())


def test_deal_requires_a_target() -> None:
    deal_id = "deal_00"
    task = _task(deal_id, "only")
    with pytest.raises(ValueError):
        DealGraph(
            deal_id=deal_id,
            tasks={task.task_id: task},
            edges=frozenset(),
            targets=frozenset(),
        )

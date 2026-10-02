"""DAG helpers for deal task graphs. Edges point from predecessor to successor."""

from __future__ import annotations


class CycleError(ValueError):
    """Raised when a deal graph contains a directed cycle."""


def predecessors(edges: frozenset[tuple[str, str]] | set[tuple[str, str]], task_id: str) -> tuple[str, ...]:
    return tuple(sorted(source for source, dest in edges if dest == task_id))


def successors(edges: frozenset[tuple[str, str]] | set[tuple[str, str]], task_id: str) -> tuple[str, ...]:
    return tuple(sorted(dest for source, dest in edges if source == task_id))


def descendants(edges: frozenset[tuple[str, str]] | set[tuple[str, str]], task_id: str) -> frozenset[str]:
    """Tasks reachable by following outgoing edges, excluding the task itself."""

    seen: set[str] = set()
    stack = list(successors(edges, task_id))
    while stack:
        current = stack.pop()
        if current in seen:
            continue
        seen.add(current)
        stack.extend(successors(edges, current))
    return frozenset(seen)


def has_cycle(task_ids: set[str], edges: frozenset[tuple[str, str]] | set[tuple[str, str]]) -> bool:
    indegree = {task_id: 0 for task_id in task_ids}
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    for source, dest in edges:
        if source not in indegree or dest not in indegree:
            return True
        outgoing[source].append(dest)
        indegree[dest] += 1
    queue = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    visited = 0
    while queue:
        current = queue.pop(0)
        visited += 1
        for dest in sorted(outgoing[current]):
            indegree[dest] -= 1
            if indegree[dest] == 0:
                queue.append(dest)
                queue.sort()
    return visited != len(task_ids)


def require_dag(task_ids: set[str], edges: frozenset[tuple[str, str]] | set[tuple[str, str]]) -> None:
    if has_cycle(task_ids, edges):
        raise CycleError("deal graph contains a directed cycle")


def topological_order(
    task_ids: set[str], edges: frozenset[tuple[str, str]] | set[tuple[str, str]]
) -> tuple[str, ...]:
    require_dag(task_ids, edges)
    indegree = {task_id: 0 for task_id in task_ids}
    outgoing: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    for source, dest in edges:
        outgoing[source].append(dest)
        indegree[dest] += 1
    queue = sorted(task_id for task_id, degree in indegree.items() if degree == 0)
    order: list[str] = []
    while queue:
        current = queue.pop(0)
        order.append(current)
        for dest in sorted(outgoing[current]):
            indegree[dest] -= 1
            if indegree[dest] == 0:
                queue.append(dest)
                queue.sort()
    return tuple(order)

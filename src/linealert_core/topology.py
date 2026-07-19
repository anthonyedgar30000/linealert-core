"""Deterministic physical and logical dependency topology."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DependencyEdge:
    """One directed dependency in the machine process graph."""

    upstream: str
    downstream: str

    def __post_init__(self) -> None:
        if not self.upstream.strip() or not self.downstream.strip():
            raise ValueError("dependency endpoints must not be empty")
        if self.upstream == self.downstream:
            raise ValueError("a dependency cannot point to itself")


@dataclass(frozen=True, slots=True)
class TopologyContext:
    """Machine context surrounding a timing relationship."""

    upstream: str
    downstream: str
    upstream_dependencies: tuple[str, ...]
    downstream_dependencies: tuple[str, ...]


class TopologyGraph:
    """Acyclic directed graph used for bounded diagnostic localization."""

    def __init__(self, edges: list[DependencyEdge]) -> None:
        if not edges:
            raise ValueError("topology requires at least one dependency edge")
        if len(edges) != len(set(edges)):
            raise ValueError("topology dependencies must be unique")

        self._edges = tuple(edges)
        self._adjacency: dict[str, set[str]] = {}
        self._reverse: dict[str, set[str]] = {}

        for edge in self._edges:
            self._adjacency.setdefault(edge.upstream, set()).add(edge.downstream)
            self._adjacency.setdefault(edge.downstream, set())
            self._reverse.setdefault(edge.downstream, set()).add(edge.upstream)
            self._reverse.setdefault(edge.upstream, set())

        self._order = self._topological_order()
        self._rank = {node: index for index, node in enumerate(self._order)}

    def has_edge(self, upstream: str, downstream: str) -> bool:
        return downstream in self._adjacency.get(upstream, set())

    def context_for_edge(self, upstream: str, downstream: str) -> TopologyContext:
        if not self.has_edge(upstream, downstream):
            raise ValueError(f"unknown topology edge: {upstream} -> {downstream}")
        return TopologyContext(
            upstream=upstream,
            downstream=downstream,
            upstream_dependencies=self._walk(upstream, self._reverse),
            downstream_dependencies=self._walk(downstream, self._adjacency),
        )

    def _walk(
        self,
        start: str,
        adjacency: dict[str, set[str]],
    ) -> tuple[str, ...]:
        visited: set[str] = set()
        queue = deque(sorted(adjacency[start]))

        while queue:
            node = queue.popleft()
            if node in visited:
                continue
            visited.add(node)
            queue.extend(sorted(adjacency[node]))

        return tuple(sorted(visited, key=self._rank.__getitem__))

    def _topological_order(self) -> tuple[str, ...]:
        indegree = {node: 0 for node in self._adjacency}
        for downstream_nodes in self._adjacency.values():
            for downstream in downstream_nodes:
                indegree[downstream] += 1

        ready = deque(sorted(node for node, degree in indegree.items() if degree == 0))
        ordered: list[str] = []

        while ready:
            node = ready.popleft()
            ordered.append(node)
            for downstream in sorted(self._adjacency[node]):
                indegree[downstream] -= 1
                if indegree[downstream] == 0:
                    ready.append(downstream)

        if len(ordered) != len(indegree):
            raise ValueError("topology dependencies must be acyclic")
        return tuple(ordered)

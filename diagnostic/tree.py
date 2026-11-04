"""The skill tree: a DAG with multi-parent (poly-hierarchy) nodes.

Status rules (project spec section 4.2):
  LOCKED     some parent has not been passed yet
  AVAILABLE  every parent is passed, and the node itself is not mastered
  MASTERED   every parent is passed and the node's own ratio >= thresholds.master

A node counts as "passed" for unlocking its children when
its own ratio >= thresholds.unlock and it is not LOCKED itself.
"""
from __future__ import annotations

from collections import deque
from typing import Dict, Iterable, List, Mapping, Optional

from .models import AVAILABLE, FACETS, LOCKED, MASTERED, Node, NodePoints, NodeState


class TreeError(ValueError):
    pass


class SkillTree:
    def __init__(self, nodes: Iterable[Node]):
        self.nodes: Dict[str, Node] = {}
        for node in nodes:
            if node.id in self.nodes:
                raise TreeError(f"duplicate node id {node.id!r}")
            self.nodes[node.id] = node
        problems = self.problems()
        if problems:
            raise TreeError("; ".join(problems))
        self.order: List[str] = self._topological_order()
        self.children: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for node in self.nodes.values():
            for parent in node.parents:
                self.children[parent].append(node.id)

    # Structure ---------------------------------------------------------
    def problems(self) -> List[str]:
        errors = []
        for node in self.nodes.values():
            for parent in node.parents:
                if parent not in self.nodes:
                    errors.append(f"node {node.id!r} names an unknown parent {parent!r}")
            if len(set(node.parents)) != len(node.parents):
                errors.append(f"node {node.id!r} lists a parent twice")
        if not errors and self._topological_order(check_only=True) is None:
            errors.append("the skill tree has a cycle")
        return errors

    def _topological_order(self, check_only: bool = False) -> Optional[List[str]]:
        indegree = {nid: len(n.parents) for nid, n in self.nodes.items()}
        kids: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for node in self.nodes.values():
            for parent in node.parents:
                if parent in kids:
                    kids[parent].append(node.id)
        queue = deque(nid for nid in self.nodes if indegree[nid] == 0)
        order: List[str] = []
        while queue:
            nid = queue.popleft()
            order.append(nid)
            for child in kids[nid]:
                indegree[child] -= 1
                if indegree[child] == 0:
                    queue.append(child)
        if len(order) != len(self.nodes):
            return None
        return order

    def node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def concept_nodes(self, concept: str) -> List[Node]:
        return [self.nodes[nid] for nid in self.order if self.nodes[nid].concept == concept]

    def concepts(self) -> List[str]:
        seen: List[str] = []
        for nid in self.order:
            if self.nodes[nid].concept not in seen:
                seen.append(self.nodes[nid].concept)
        return seen

    def multi_parent_nodes(self) -> List[str]:
        return [nid for nid in self.order if len(self.nodes[nid].parents) > 1]

    # Evaluation --------------------------------------------------------
    def evaluate(self, points: Mapping[str, NodePoints], unlock: float, master: float) -> Dict[str, NodeState]:
        states: Dict[str, NodeState] = {}
        passed: Dict[str, bool] = {}
        for nid in self.order:
            node = self.nodes[nid]
            pts = points.get(nid) or NodePoints()
            ratio = pts.ratio
            parents_ok = all(passed.get(p, False) for p in node.parents)
            if not parents_ok:
                status = LOCKED
            elif ratio is not None and ratio >= master:
                status = MASTERED
            else:
                status = AVAILABLE
            passed[nid] = parents_ok and ratio is not None and ratio >= unlock
            facets = {f: (pts.earned[f] / pts.possible[f] if pts.possible[f] else None) for f in FACETS}
            states[nid] = NodeState(status=status, ratio=ratio, evidence=pts.evidence, facets=facets)
        return states

"""Pydantic models for the lesson session knowledge graph."""

from __future__ import annotations

import json
import time
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator


class NodeType(str, Enum):
    goal = "goal"
    observation = "observation"
    hypothesis = "hypothesis"
    attempt = "attempt"
    concept = "concept"
    resolution = "resolution"


class EdgeType(str, Enum):
    motivated = "motivated"
    produced = "produced"
    revealed = "revealed"
    contradicted = "contradicted"
    seemed_to_confirm = "seemed_to_confirm"
    assumed_about = "assumed_about"
    involves = "involves"
    enabled = "enabled"
    achieves = "achieves"


class Node(BaseModel):
    id: str
    type: NodeType
    label: str
    flags: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_root_cause(self) -> bool:
        return bool(self.flags.get("root_cause"))

    @property
    def is_misconception(self) -> bool:
        return bool(self.flags.get("misconception"))

    @property
    def is_pivotal(self) -> bool:
        return bool(self.flags.get("pivotal"))


class Edge(BaseModel):
    from_id: str
    to_id: str
    type: EdgeType


class SessionGraph(BaseModel):
    schema_version: str = "2"
    slug: str
    goal: str = ""
    total_events_compressed: int = 0
    root_cause_id: str | None = None
    resolution_id: str | None = None
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_referential_integrity(self) -> "SessionGraph":
        ids = {n.id for n in self.nodes}
        if self.root_cause_id and self.root_cause_id not in ids:
            self.root_cause_id = None
        if self.resolution_id and self.resolution_id not in ids:
            self.resolution_id = None
        return self

    # ------------------------------------------------------------------
    # Convenience accessors
    # ------------------------------------------------------------------

    def node_by_id(self, node_id: str) -> Node | None:
        for n in self.nodes:
            if n.id == node_id:
                return n
        return None

    def nodes_of_type(self, t: NodeType) -> list[Node]:
        return [n for n in self.nodes if n.type == t]

    def edges_to(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.to_id == node_id]

    def edges_from(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.from_id == node_id]

    # ------------------------------------------------------------------
    # ID allocation
    # ------------------------------------------------------------------

    def _next_id(self, prefix: str) -> str:
        existing = [n.id for n in self.nodes if n.id.startswith(prefix)]
        nums = []
        for eid in existing:
            try:
                nums.append(int(eid[len(prefix):]))
            except ValueError:
                pass
        return f"{prefix}{max(nums, default=0) + 1}"

    def alloc_id(self, node_type: NodeType) -> str:
        prefix_map = {
            NodeType.goal: "g",
            NodeType.observation: "o",
            NodeType.hypothesis: "h",
            NodeType.attempt: "a",
            NodeType.concept: "c",
            NodeType.resolution: "r",
        }
        return self._next_id(prefix_map[node_type])

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "SessionGraph":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def save(self, path: Path) -> int:
        text = self.model_dump_json(indent=2)
        path.write_text(text, encoding="utf-8")
        return len(text)

    @classmethod
    def empty(cls, slug: str, goal: str = "") -> "SessionGraph":
        graph = cls(slug=slug, goal=goal)
        graph.nodes.append(Node(id="g1", type=NodeType.goal, label=goal or slug))
        return graph


class RawEvent(BaseModel):
    """One line from arc.jsonl."""

    ts: float = Field(default_factory=time.time)
    tool: str
    args: str = ""
    result_head: str = ""
    is_error: bool = False
    significant: bool = False
    score: float = 0.0

    @classmethod
    def from_jsonl_line(cls, line: str) -> "RawEvent | None":
        try:
            return cls.model_validate_json(line.strip())
        except Exception:
            return None

    @classmethod
    def load_file(cls, path: Path) -> list["RawEvent"]:
        events: list[RawEvent] = []
        try:
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.strip():
                    ev = cls.from_jsonl_line(line)
                    if ev is not None:
                        events.append(ev)
        except FileNotFoundError:
            pass
        return events

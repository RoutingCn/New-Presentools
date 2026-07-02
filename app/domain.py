from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class LockedArtifactError(RuntimeError):
    """Raised when code attempts to replace an immutable artifact."""


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class Event:
    id: str
    project_id: str
    kind: str
    at: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ContentNode:
    id: str
    kind: str
    title: str
    body: str
    source_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class Proposal:
    id: str
    title: str
    rationale: str
    changes: tuple[dict[str, Any], ...]
    affected_ids: tuple[str, ...]
    status: str = "pending"


@dataclass(frozen=True)
class Artifact:
    id: str
    name: str
    node_ids: tuple[str, ...]
    locked: bool
    created_at: str
    html: str = ""


@dataclass
class ProjectState:
    id: str
    title: str
    audience: str
    stage: str = "contract"
    content_nodes: list[ContentNode] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    artifacts: list[Artifact] = field(default_factory=list)

    @property
    def contract(self) -> dict[str, str]:
        return {"title": self.title, "audience": self.audience}

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "audience": self.audience,
            "stage": self.stage,
            "content_nodes": [asdict(node) for node in self.content_nodes],
            "proposals": [asdict(proposal) for proposal in self.proposals],
            "artifacts": [asdict(artifact) for artifact in self.artifacts],
        }


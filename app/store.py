from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any

from .domain import (
    Artifact,
    ContentNode,
    Event,
    LockedArtifactError,
    ProjectState,
    Proposal,
    new_id,
    utc_now,
)


class EventStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def event_path(self, project_id: str) -> Path:
        return self.root / f"{project_id}.jsonl"

    def append(self, project_id: str, kind: str, payload: dict[str, Any]) -> Event:
        event = Event(new_id("evt"), project_id, kind, utc_now(), payload)
        with self.event_path(project_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")
        return event

    def events(self, project_id: str) -> list[Event]:
        path = self.event_path(project_id)
        if not path.exists():
            return []
        result = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                result.append(Event(**json.loads(line)))
        return result

    def create_project(self, title: str, audience: str) -> ProjectState:
        project_id = new_id("prj")
        self.append(
            project_id,
            "project.created",
            {"title": title.strip(), "audience": audience.strip()},
        )
        return self.project(project_id)

    def add_content_node(
        self,
        project_id: str,
        *,
        kind: str,
        title: str,
        body: str,
        source_ids: list[str] | None = None,
    ) -> ContentNode:
        node = ContentNode(
            id=new_id("node"),
            kind=kind,
            title=title,
            body=body,
            source_ids=tuple(source_ids or ()),
        )
        self.append(project_id, "content.added", {"node": node.__dict__})
        return node

    def create_proposal(
        self,
        project_id: str,
        *,
        title: str,
        rationale: str,
        changes: list[dict[str, Any]],
        affected_ids: list[str],
    ) -> Proposal:
        proposal = Proposal(
            id=new_id("prop"),
            title=title,
            rationale=rationale,
            changes=tuple(changes),
            affected_ids=tuple(affected_ids),
        )
        self.append(
            project_id,
            "proposal.created",
            {
                "proposal": {
                    **proposal.__dict__,
                    "changes": list(proposal.changes),
                    "affected_ids": list(proposal.affected_ids),
                }
            },
        )
        return proposal

    def accept_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        state = self.project(project_id)
        proposal = next(item for item in state.proposals if item.id == proposal_id)
        if proposal.status != "pending":
            return proposal
        created_nodes = []
        for change in proposal.changes:
            created_nodes.append(
                {
                    "id": new_id("node"),
                    "kind": change["kind"],
                    "title": change["title"],
                    "body": change["body"],
                    "source_ids": change.get("source_ids", []),
                }
            )
        self.append(
            project_id,
            "proposal.accepted",
            {"proposal_id": proposal_id, "created_nodes": created_nodes},
        )
        accepted = next(item for item in self.project(project_id).proposals if item.id == proposal_id)
        return accepted

    def lock_artifact(
        self,
        project_id: str,
        name: str,
        node_ids: list[str],
        html: str = "",
    ) -> Artifact:
        artifact = Artifact(new_id("art"), name, tuple(node_ids), True, utc_now(), html)
        self.append(
            project_id,
            "artifact.locked",
            {
                "artifact": {
                    **artifact.__dict__,
                    "node_ids": list(artifact.node_ids),
                }
            },
        )
        return artifact

    def replace_locked_artifact(
        self,
        project_id: str,
        artifact_id: str,
        node_ids: list[str],
    ) -> None:
        artifact = next(item for item in self.project(project_id).artifacts if item.id == artifact_id)
        if artifact.locked:
            raise LockedArtifactError(f"Artifact {artifact_id} is locked")
        raise NotImplementedError("Only locked artifacts are supported in the MVP")

    def context(self, project_id: str) -> dict[str, Any]:
        state = self.project(project_id)
        return state.to_dict()

    def project(self, project_id: str) -> ProjectState:
        state: ProjectState | None = None
        for event in self.events(project_id):
            if event.kind == "project.created":
                state = ProjectState(
                    id=project_id,
                    title=event.payload["title"],
                    audience=event.payload["audience"],
                )
                continue
            if state is None:
                raise ValueError(f"Project {project_id} has no creation event")
            if event.kind == "content.added":
                raw = event.payload["node"]
                state.content_nodes.append(
                    ContentNode(
                        **{
                            **raw,
                            "source_ids": tuple(raw.get("source_ids", ())),
                        }
                    )
                )
            elif event.kind == "proposal.created":
                raw = event.payload["proposal"]
                state.proposals.append(
                    Proposal(
                        **{
                            **raw,
                            "changes": tuple(raw["changes"]),
                            "affected_ids": tuple(raw["affected_ids"]),
                        }
                    )
                )
            elif event.kind == "proposal.accepted":
                proposal_id = event.payload["proposal_id"]
                state.proposals = [
                    replace(item, status="accepted") if item.id == proposal_id else item
                    for item in state.proposals
                ]
                stage = "structure"
                for raw in event.payload["created_nodes"]:
                    state.content_nodes.append(
                        ContentNode(
                            **{
                                **raw,
                                "source_ids": tuple(raw.get("source_ids", ())),
                            }
                        )
                    )
                    if raw.get("kind") == "script":
                        stage = "script"
                state.stage = stage
            elif event.kind == "artifact.locked":
                raw = event.payload["artifact"]
                state.artifacts.append(
                    Artifact(**{**raw, "node_ids": tuple(raw["node_ids"])})
                )
                state.stage = "locked"
        if state is None:
            raise KeyError(project_id)
        return state

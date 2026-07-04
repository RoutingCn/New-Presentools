from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Any, Iterator

from .domain import (
    Artifact,
    ConflictError,
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
        raw = event.to_dict()
        with self.event_path(project_id).open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(raw, ensure_ascii=False) + "\n")
        return event

    def events(self, project_id: str) -> list[Event]:
        return list(self.iter_events(project_id))

    def iter_events(self, project_id: str) -> Iterator[Event]:
        path = self.event_path(project_id)
        if not path.exists():
            return
        with path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if stripped:
                    yield Event(**json.loads(stripped))

    def compact_events(self, project_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for event in self.iter_events(project_id):
            kind_base = event.kind.rsplit(".", 1)[0]
            counts[kind_base] = counts.get(kind_base, 0) + 1
        total = sum(counts.values())
        if total >= 500:
            return {"_compaction_recommended": True, "total": total, **counts}
        return {"total": total, **counts}

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

    def accept_proposal(
        self,
        project_id: str,
        proposal_id: str,
        expected_version: int | None = None,
    ) -> Proposal:
        state = self.project(project_id)
        proposal = next(item for item in state.proposals if item.id == proposal_id)
        if proposal.status != "pending":
            return proposal

        if expected_version is not None and state.content_version != expected_version:
            raise ConflictError(
                f"Content version mismatch: expected {expected_version}, "
                f"got {state.content_version}. A newer change has been applied."
            )

        created_nodes = []
        updated_nodes = []
        deprecated_ids = []
        for change in proposal.changes:
            operation = change.get("operation", "create")
            if operation == "update":
                node_id = change["node_id"]
                current = next(node for node in state.content_nodes if node.id == node_id)
                version_before = change.get("version_before")
                if version_before is not None and current.version != version_before:
                    raise ConflictError(
                        f"Node {node_id} version mismatch: expected {version_before}, "
                        f"got {current.version}. The node was modified since this proposal was created."
                    )
                updated_nodes.append(
                    {
                        "id": node_id,
                        "kind": change.get("kind", current.kind),
                        "title": change.get("title", current.title),
                        "body": change.get("body", current.body),
                        "source_ids": change.get("source_ids", list(current.source_ids)),
                        "version": current.version + 1,
                    }
                )
            elif operation == "delete":
                deprecated_ids.append(change["node_id"])
            else:
                created_nodes.append(
                    {
                        "id": new_id("node"),
                        "kind": change["kind"],
                        "title": change["title"],
                        "body": change["body"],
                        "source_ids": change.get("source_ids", []),
                        "version": 1,
                    }
                )
        new_version = state.content_version + 1
        self.append(
            project_id,
            "proposal.accepted",
            {
                "proposal_id": proposal_id,
                "created_nodes": created_nodes,
                "updated_nodes": updated_nodes,
                "deprecated_ids": deprecated_ids,
                "content_version": new_version,
            },
        )
        accepted = next(
            item for item in self.project(project_id).proposals if item.id == proposal_id
        )
        return accepted

    def reject_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        state = self.project(project_id)
        proposal = next(item for item in state.proposals if item.id == proposal_id)
        if proposal.status != "pending":
            return proposal
        self.append(project_id, "proposal.rejected", {"proposal_id": proposal_id})
        return next(
            item for item in self.project(project_id).proposals if item.id == proposal_id
        )

    def preview_artifact(
        self,
        project_id: str,
        name: str,
        node_ids: list[str],
        html: str,
    ) -> Artifact:
        artifact = Artifact(new_id("art"), name, tuple(node_ids), False, utc_now(), html)
        self.append(
            project_id,
            "artifact.previewed",
            {
                "artifact": {
                    **artifact.__dict__,
                    "node_ids": list(artifact.node_ids),
                }
            },
        )
        return artifact

    def lock_preview_artifact(self, project_id: str, artifact_id: str) -> Artifact:
        state = self.project(project_id)
        preview = next(item for item in state.artifacts if item.id == artifact_id)
        artifact = replace(preview, locked=True)
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
        artifact = next(
            item for item in self.project(project_id).artifacts if item.id == artifact_id
        )
        if artifact.locked:
            raise LockedArtifactError(f"Artifact {artifact_id} is locked")
        raise NotImplementedError("Only locked artifacts are supported in the MVP")

    def context(self, project_id: str) -> dict[str, Any]:
        state = self.project(project_id)
        return state.to_dict()

    def project(self, project_id: str) -> ProjectState:
        state: ProjectState | None = None
        for event in self.iter_events(project_id):
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
                created_nodes = event.payload.get("created_nodes", [])
                updated_nodes = event.payload.get("updated_nodes", [])
                deprecated_ids = set(event.payload.get("deprecated_ids", []))
                if "content_version" in event.payload:
                    state.content_version = event.payload["content_version"]
                else:
                    state.bump_version()
                stage = state.stage
                for raw in created_nodes:
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
                    else:
                        stage = "structure"
                for raw in updated_nodes:
                    replacement = ContentNode(
                        **{
                            **raw,
                            "source_ids": tuple(raw.get("source_ids", ())),
                        }
                    )
                    state.content_nodes = [
                        replacement if node.id == replacement.id else node
                        for node in state.content_nodes
                    ]
                if deprecated_ids:
                    state.content_nodes = [
                        node for node in state.content_nodes if node.id not in deprecated_ids
                    ]
                state.stage = stage
            elif event.kind == "proposal.rejected":
                proposal_id = event.payload["proposal_id"]
                state.proposals = [
                    replace(item, status="rejected") if item.id == proposal_id else item
                    for item in state.proposals
                ]
            elif event.kind == "artifact.previewed":
                raw = event.payload["artifact"]
                state.artifacts.append(
                    Artifact(**{**raw, "node_ids": tuple(raw["node_ids"])})
                )
            elif event.kind == "artifact.locked":
                raw = event.payload["artifact"]
                artifact = Artifact(**{**raw, "node_ids": tuple(raw["node_ids"])})
                state.artifacts = [
                    artifact if item.id == artifact.id else item
                    for item in state.artifacts
                ]
                if all(item.id != artifact.id for item in state.artifacts):
                    state.artifacts.append(artifact)
                state.artifacts = sorted(
                    state.artifacts,
                    key=lambda item: item.created_at,
                )
                state.stage = "locked"
        if state is None:
            raise KeyError(project_id)
        return state

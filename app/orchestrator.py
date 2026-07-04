from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .agents import AgentDelivery, AgentProvider
from .aesthetic_html import AestheticHtmlProvider
from .domain import Artifact, ContentNode, ProjectState, Proposal
from .html_provider import HtmlProvider
from .store import EventStore


@dataclass(frozen=True)
class AnalysisResult:
    deliveries: dict[str, AgentDelivery]
    proposal: Proposal

    def to_dict(self) -> dict[str, Any]:
        return {
            "deliveries": {
                role: delivery.to_dict()
                for role, delivery in self.deliveries.items()
            },
            "proposal": {
                **self.proposal.__dict__,
                "changes": list(self.proposal.changes),
                "affected_ids": list(self.proposal.affected_ids),
            },
        }


class Controller:
    ROLES = ("content", "research", "visual", "creative")

    def __init__(
        self,
        store: EventStore,
        provider: AgentProvider,
        html_provider: HtmlProvider | None = None,
    ):
        self.store = store
        self.provider = provider
        self.html_provider = html_provider or AestheticHtmlProvider()

    def create_project(self, title: str, audience: str) -> ProjectState:
        return self.store.create_project(title, audience)

    def analyze_topic(self, project_id: str) -> AnalysisResult:
        project = self.store.project(project_id)
        deliveries: dict[str, AgentDelivery] = {}
        for role in self.ROLES:
            delivery = self.provider.run(role, project.contract, self.store.context(project_id))
            self._validate_delivery(delivery)
            deliveries[role] = delivery
            self.store.append(
                project_id,
                "agent.completed",
                {"delivery": delivery.to_dict()},
            )
        changes = self._deduplicate_changes([
            output
            for role in self.ROLES
            for output in deliveries[role].outputs
        ])
        affected_ids = sorted(
            {
                item
                for delivery in deliveries.values()
                for item in delivery.affected_ids
            }
        )
        proposal = self.store.create_proposal(
            project_id,
            title="采用多 Agent 深度分析结构",
            rationale=(
                "四个专业角色已按概念、关系、例子和表达质量完成自检，"
                "总控将输出合并为可审阅、可修改的初始内容结构。"
            ),
            changes=changes,
            affected_ids=affected_ids,
        )
        return AnalysisResult(deliveries, proposal)

    def accept_proposal(
        self,
        project_id: str,
        proposal_id: str,
        expected_version: int | None = None,
    ) -> Proposal:
        return self.store.accept_proposal(project_id, proposal_id, expected_version)

    def reject_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        return self.store.reject_proposal(project_id, proposal_id)

    def generate_script(self, project_id: str) -> Proposal:
        state = self.store.project(project_id)
        structure_nodes = [
            node for node in state.content_nodes
            if node.kind != "script"
        ]
        if not structure_nodes:
            raise ValueError("逐字稿生成需要已批准的内容结构")

        delivery = self.provider.run(
            "script",
            state.contract | {"node_count": len(structure_nodes)},
            self.store.context(project_id),
        )
        self._validate_delivery(delivery)
        self.store.append(
            project_id,
            "agent.completed",
            {"delivery": delivery.to_dict()},
        )
        changes = self._deduplicate_changes([
            {
                "kind": "script",
                "title": f"逐字稿：{output['title']}",
                "body": output["body"],
                "source_ids": [node.id for node in structure_nodes],
            }
            for output in delivery.outputs
        ])
        return self.store.create_proposal(
            project_id,
            title="生成逐字稿",
            rationale=(
                "通过脚本 Agent 将已批准的内容结构转化为可继续修改的专业讲述稿，"
                "保留来源节点，方便回溯、下载和再编辑。"
            ),
            changes=changes,
            affected_ids=[node.id for node in structure_nodes],
        )

    def submit_comment(
        self,
        project_id: str,
        text: str,
        target_id: str | None = None,
    ) -> Proposal:
        state = self.store.project(project_id)
        comment = text.strip()
        if not comment:
            raise ValueError("意见不能为空")
        target = next(
            (node for node in state.content_nodes if node.id == target_id),
            None,
        )
        affected_ids = [target.id] if target else []
        target_title = target.title if target else "项目整体"
        target_body = target.body if target else "这条意见针对项目整体结构、表达或成果策略。"
        self.store.append(
            project_id,
            "comment.added",
            {"text": comment, "target_id": target.id if target else None},
        )
        return self.store.create_proposal(
            project_id,
            title=f"根据讨论修订：{target_title}",
            rationale=(
                "总控已将讨论意见转化为可审阅的修改提案。批准后会写入全量内容版；"
                "已锁定成果不会被直接改写。"
            ),
            changes=self._deduplicate_changes([
                {
                    "kind": "revision",
                    "title": f"修订建议：{target_title}",
                    "body": (
                        f"原内容基础：{target_body}\n"
                        f"讨论意见：{comment}\n"
                        "修订方向：围绕该意见补充概念、关系、例子或反方观点，"
                        "让内容更具体、更自洽，并保持语言通顺。"
                    ),
                    "source_ids": affected_ids,
                }
            ]),
            affected_ids=affected_ids,
        )

    def revise_node(
        self,
        project_id: str,
        node_id: str,
        title: str,
        body: str,
    ) -> Proposal:
        state = self.store.project(project_id)
        node = next(item for item in state.content_nodes if item.id == node_id)
        new_title = title.strip() or node.title
        new_body = body.strip()
        if not new_body:
            raise ValueError("修订内容不能为空")
        return self.store.create_proposal(
            project_id,
            title=f"修改内容对象：{node.title}",
            rationale="用户发起对象级修改。批准后只更新该对象，并保留提案记录和版本号。",
            changes=[
                {
                    "operation": "update",
                    "node_id": node.id,
                    "kind": node.kind,
                    "title": new_title,
                    "body": new_body,
                    "source_ids": list(node.source_ids),
                    "version_before": node.version,
                    "before": {"title": node.title, "body": node.body},
                }
            ],
            affected_ids=[node.id],
        )

    def delete_node(self, project_id: str, node_id: str, reason: str = "") -> Proposal:
        state = self.store.project(project_id)
        node = next(item for item in state.content_nodes if item.id == node_id)
        return self.store.create_proposal(
            project_id,
            title=f"删除内容对象：{node.title}",
            rationale=reason.strip() or (
                "用户发起对象级删除。批准后该对象会从当前全量内容版移除，"
                "历史仍保留。逐字稿和 HTML 预览可能过期。"
            ),
            changes=[
                {
                    "operation": "delete",
                    "node_id": node.id,
                    "kind": node.kind,
                    "title": node.title,
                    "body": node.body,
                }
            ],
            affected_ids=[node.id],
        )

    def preview_html(self, project_id: str, name: str = "HTML 预览") -> Artifact:
        state = self.store.project(project_id)
        structure_nodes = tuple(
            node for node in state.content_nodes if node.kind != "script"
        )
        if not structure_nodes:
            raise ValueError("HTML 预览需要已批准的内容结构")
        html = self.html_provider.render(state, structure_nodes)
        return self.store.preview_artifact(
            project_id,
            name,
            [node.id for node in structure_nodes],
            html,
        )

    def lock_html_preview(self, project_id: str, artifact_id: str) -> Artifact:
        return self.store.lock_preview_artifact(project_id, artifact_id)

    def lock_artifact(self, project_id: str, name: str) -> Artifact:
        state = self.store.project(project_id)
        structure_nodes = tuple(
            node for node in state.content_nodes if node.kind != "script"
        )
        html = self.html_provider.render(state, structure_nodes)
        return self.store.lock_artifact(
            project_id,
            name,
            [node.id for node in structure_nodes],
            html,
        )

    def memory_markdown(self, project_id: str) -> str:
        state = self.store.project(project_id)
        agent_events = [
            event for event in self.store.iter_events(project_id)
            if event.kind == "agent.completed"
        ]
        compaction = self.store.compact_events(project_id)
        lines = [
            "# 项目记忆",
            "",
            "## 任务契约",
            f"- 主题：{state.title}",
            f"- 受众：{state.audience}",
            f"- 当前阶段：{state.stage}",
            f"- 内容版本：{state.content_version}",
            f"- 过程事件：{compaction.get('total', len(list(self.store.iter_events(project_id))))} 条",
        ]
        if compaction.get("_compaction_recommended"):
            lines.append("- ⚠ 事件已超过 500 条，建议执行压缩以提升性能。")
        lines.extend(["", "## Agent 结论"])
        for event in agent_events:
            delivery = event.payload["delivery"]
            lines.append(f"- **{delivery['agent']}**：{delivery['summary']}")
        gaps = [
            uncertainty
            for event in agent_events
            for uncertainty in event.payload["delivery"]["uncertainties"]
        ]
        lines.extend(["", "## 证据缺口"])
        if gaps:
            lines.extend(f"- {gap}" for gap in gaps if gap)
        else:
            lines.append("- 暂无")
        lines.extend(["", "## 已采用内容"])
        lines.extend(
            f"- [{node.kind}] v{node.version} {node.title}：{node.body}"
            for node in state.content_nodes
        )
        lines.extend(["", "## 版本与锁定成果"])
        if state.artifacts:
            for artifact in state.artifacts:
                status = "已锁定" if artifact.locked else "预览中"
                lines.append(
                    f"- {artifact.name}（{artifact.id}）：{status}，"
                    f"包含 {len(artifact.node_ids)} 个内容对象"
                )
        else:
            lines.append("- 尚无锁定成果")
        lines.extend(["", "## 下一步", "- 补齐证据后进入结构与 HTML 生产。"])
        return "\n".join(lines) + "\n"

    def events(self, project_id: str):
        return self.store.events(project_id)

    @staticmethod
    def _validate_delivery(delivery: AgentDelivery) -> None:
        if not delivery.summary or not delivery.outputs:
            raise ValueError(f"{delivery.agent} 返回了不完整的交付")
        if not delivery.quality_checks or not delivery.next_action:
            raise ValueError(f"{delivery.agent} 未完成质量合约")

    @staticmethod
    def _deduplicate_changes(changes: list[dict[str, Any]]) -> list[dict[str, Any]]:
        seen_bodies: set[str] = set()
        title_counts: dict[tuple[str, str], int] = {}
        result: list[dict[str, Any]] = []
        for change in changes:
            body_key = _normalize_for_duplicate_check(change.get("body", ""))
            if body_key and body_key in seen_bodies:
                continue
            if body_key:
                seen_bodies.add(body_key)

            item = dict(change)
            kind = str(item.get("kind", "")).strip()
            title = str(item.get("title", "")).strip()
            title_key = (kind, _normalize_for_duplicate_check(title))
            count = title_counts.get(title_key, 0) + 1
            title_counts[title_key] = count
            if count > 1 and title:
                item["title"] = f"{title}（{count}）"
            result.append(item)
        return result


def _normalize_for_duplicate_check(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"\s+", "", text)

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
            title="采用多 Agent 顶级标准分析",
            rationale=(
                "四个专业角色已按概念、关系、例子和表达质量完成自检，"
                "总控将输出合并为可审阅、可修改的初始内容结构。"
            ),
            changes=changes,
            affected_ids=affected_ids,
        )
        return AnalysisResult(deliveries, proposal)

    def accept_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        return self.store.accept_proposal(project_id, proposal_id)

    def reject_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        return self.store.reject_proposal(project_id, proposal_id)

    def generate_script(self, project_id: str) -> Proposal:
        state = self.store.project(project_id)
        structure_nodes = [
            node for node in state.content_nodes
            if node.kind != "script"
        ]
        if not structure_nodes:
            raise ValueError("Script generation requires accepted content structure")
        changes = self._deduplicate_changes([
            _script_change(node) for node in structure_nodes
        ])
        return self.store.create_proposal(
            project_id,
            title="生成逐字稿",
            rationale=(
                "将已批准的内容结构转化为可继续修改的专业讲述稿，"
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
            raise ValueError("Comment cannot be empty")
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
            raise ValueError("Revision body cannot be empty")
        return self.store.create_proposal(
            project_id,
            title=f"修改内容对象：{node.title}",
            rationale="用户发起对象级修改。批准后只更新该对象，并保留提案记录。",
            changes=[
                {
                    "operation": "update",
                    "node_id": node.id,
                    "kind": node.kind,
                    "title": new_title,
                    "body": new_body,
                    "source_ids": list(node.source_ids),
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
            rationale=reason.strip() or "用户发起对象级删除。批准后该对象会从当前全量内容版移除，历史仍保留。",
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
            raise ValueError("HTML preview requires accepted content structure")
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
            event for event in self.store.events(project_id)
            if event.kind == "agent.completed"
        ]
        lines = [
            "# 项目记忆",
            "",
            "## 任务契约",
            f"- 主题：{state.title}",
            f"- 受众：{state.audience}",
            f"- 当前阶段：{state.stage}",
            f"- 过程事件：{len(self.store.events(project_id))} 条",
            "",
            "## Agent 结论",
        ]
        for event in agent_events:
            delivery = event.payload["delivery"]
            lines.append(f"- **{delivery['agent']}**：{delivery['summary']}")
        gaps = [
            uncertainty
            for event in agent_events
            for uncertainty in event.payload["delivery"]["uncertainties"]
        ]
        lines.extend(["", "## 证据缺口"])
        lines.extend(f"- {gap}" for gap in gaps if gap)
        lines.extend(["", "## 已采用内容"])
        lines.extend(
            f"- [{node.kind}] {node.title}：{node.body}"
            for node in state.content_nodes
        )
        lines.extend(["", "## 版本与锁定成果"])
        if state.artifacts:
            lines.extend(
                f"- {artifact.name}（{artifact.id}）：已锁定，包含 {len(artifact.node_ids)} 个内容对象"
                for artifact in state.artifacts
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
            raise ValueError(f"{delivery.agent} returned an incomplete delivery")
        if not delivery.quality_checks or not delivery.next_action:
            raise ValueError(f"{delivery.agent} did not complete its quality contract")

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


def _script_change(node: ContentNode) -> dict[str, Any]:
    return {
        "kind": "script",
        "title": f"逐字稿：{node.title}",
        "body": (
            f"开场意图：这一段先把“{node.title}”讲清楚，让听众知道它在整体论证中的位置，"
            "而不是把它当成孤立页面。\n"
            "讲述逻辑：先定义这一节点的核心含义，再说明它和前后内容之间的关系，"
            f"最后回到听众最关心的判断或行动。具体内容是：{node.body}\n"
            "例子：可以用一个真实工作场景、业务案例或材料片段帮助听众把抽象判断落到经验里；"
            "例子必须服务观点，不能抢走主线。\n"
            "转场：讲完这一点后，要自然连接到下一层证据、反方问题或行动方案，"
            "让整场表达保持递进。"
        ),
        "source_ids": [node.id],
    }


def _normalize_for_duplicate_check(value: Any) -> str:
    text = str(value or "").lower()
    return re.sub(r"\s+", "", text)

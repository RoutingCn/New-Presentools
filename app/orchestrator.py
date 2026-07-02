from __future__ import annotations

from html import escape
from dataclasses import dataclass
from typing import Any

from .agents import AgentDelivery, AgentProvider
from .domain import Artifact, ProjectState, Proposal
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

    def __init__(self, store: EventStore, provider: AgentProvider):
        self.store = store
        self.provider = provider

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
        changes = [
            output
            for role in self.ROLES
            for output in deliveries[role].outputs
        ]
        affected_ids = sorted(
            {
                item
                for delivery in deliveries.values()
                for item in delivery.affected_ids
            }
        )
        proposal = self.store.create_proposal(
            project_id,
            title="采用多 Agent 深度分析",
            rationale="四个专业角色已完成自检，总控将输出合并为可审阅的初始内容结构。",
            changes=changes,
            affected_ids=affected_ids,
        )
        return AnalysisResult(deliveries, proposal)

    def accept_proposal(self, project_id: str, proposal_id: str) -> Proposal:
        return self.store.accept_proposal(project_id, proposal_id)

    def generate_script(self, project_id: str) -> Proposal:
        state = self.store.project(project_id)
        structure_nodes = [
            node for node in state.content_nodes
            if node.kind != "script"
        ]
        if not structure_nodes:
            raise ValueError("Script generation requires accepted content structure")
        changes = [
            {
                "kind": "script",
                "title": f"逐字稿：{node.title}",
                "body": (
                    f"这一页先呈现“{node.title}”。\n"
                    f"讲述要点：{node.body}\n"
                    "转场：接下来把这个判断与下一层证据或行动连接起来。"
                ),
                "source_ids": [node.id],
            }
            for node in structure_nodes
        ]
        return self.store.create_proposal(
            project_id,
            title="生成逐字稿",
            rationale="将已批准的内容结构转化为可继续修改的讲述稿，保留来源节点以便回溯。",
            changes=changes,
            affected_ids=[node.id for node in structure_nodes],
        )

    def lock_artifact(self, project_id: str, name: str) -> Artifact:
        state = self.store.project(project_id)
        html = self._render_html(state)
        return self.store.lock_artifact(
            project_id,
            name,
            [node.id for node in state.content_nodes],
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
    def _render_html(state: ProjectState) -> str:
        articles = "\n".join(
            (
                f'<article class="slide" id="{escape(node.id)}">'
                f"<small>{escape(node.kind)}</small>"
                f"<h2>{escape(node.title)}</h2>"
                f"<p>{escape(node.body).replace(chr(10), '<br>')}</p>"
                "</article>"
            )
            for node in state.content_nodes
        )
        return (
            "<!doctype html>\n"
            '<html lang="zh-CN">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
            f"<title>{escape(state.title)}</title>\n"
            "<style>\n"
            "body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f6f7f9;color:#15171a;}\n"
            "main{max-width:980px;margin:0 auto;padding:48px 24px;}\n"
            "header{border-bottom:3px solid #15171a;margin-bottom:28px;padding-bottom:18px;}\n"
            "h1{font-size:34px;margin:0 0 10px;} .audience{color:#5a6472;margin:0;}\n"
            ".slide{background:white;border:1px solid #d7dce2;border-left:5px solid #15171a;margin:18px 0;padding:24px;}\n"
            ".slide small{display:block;color:#657082;text-transform:uppercase;margin-bottom:10px;}\n"
            ".slide h2{font-size:24px;margin:0 0 12px;} .slide p{font-size:18px;line-height:1.75;margin:0;}\n"
            "</style>\n"
            "</head>\n"
            "<body><main>\n"
            f"<header><h1>{escape(state.title)}</h1><p class=\"audience\">{escape(state.audience)}</p></header>\n"
            f'<section class="slides">\n{articles}\n</section>\n'
            "</main></body>\n"
            "</html>\n"
        )

    @staticmethod
    def _validate_delivery(delivery: AgentDelivery) -> None:
        if not delivery.summary or not delivery.outputs:
            raise ValueError(f"{delivery.agent} returned an incomplete delivery")
        if not delivery.quality_checks or not delivery.next_action:
            raise ValueError(f"{delivery.agent} did not complete its quality contract")

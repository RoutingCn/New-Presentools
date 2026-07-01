from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class AgentDelivery:
    agent: str
    summary: str
    outputs: tuple[dict[str, Any], ...]
    affected_ids: tuple[str, ...]
    uncertainties: tuple[str, ...]
    quality_checks: tuple[str, ...]
    next_action: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["outputs"] = list(self.outputs)
        value["affected_ids"] = list(self.affected_ids)
        value["uncertainties"] = list(self.uncertainties)
        value["quality_checks"] = list(self.quality_checks)
        return value


class AgentProvider(Protocol):
    def run(
        self,
        role: str,
        contract: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentDelivery:
        ...


class DeterministicProvider:
    """Local provider used to validate orchestration before model integration."""

    def run(
        self,
        role: str,
        contract: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentDelivery:
        title = contract["title"]
        audience = contract["audience"]
        deliveries = {
            "content": AgentDelivery(
                agent="content",
                summary=f"为“{title}”建立面向{audience}的核心论证。",
                outputs=(
                    {
                        "kind": "claim",
                        "title": "核心判断",
                        "body": "增长逻辑正在从规模扩张转向质量跃迁，竞争优势将更多来自生产率、技术与组织能力。",
                    },
                    {
                        "kind": "counterclaim",
                        "title": "最强反方",
                        "body": "外部需求和成本压力可能使企业优先收缩投资，质量跃迁并不会自动发生。",
                    },
                ),
                affected_ids=(),
                uncertainties=("需要进一步界定“下一轮”的时间范围。",),
                quality_checks=("中心论点明确", "包含反方观点", "语气适合决策者"),
                next_action="用可靠数据验证质量跃迁的关键驱动。",
            ),
            "research": AgentDelivery(
                agent="research",
                summary="建立证据清单，并明确当前无法确认的数据口径。",
                outputs=(
                    {
                        "kind": "evidence_gap",
                        "title": "证据缺口",
                        "body": "需要补充研发投入、全要素生产率与利润率之间的可比数据，并标注年份、行业和样本口径。",
                    },
                ),
                affected_ids=(),
                uncertainties=("当前为本地演示 provider，尚未执行互联网与资料目录检索。",),
                quality_checks=("事实与推断分离", "标记数据口径", "不虚构来源"),
                next_action="接入检索 provider 后执行双源调查。",
            ),
            "visual": AgentDelivery(
                agent="visual",
                summary="提出以论证关系而非页面数量组织 HTML 的视觉结构。",
                outputs=(
                    {
                        "kind": "visual_module",
                        "title": "视觉模块",
                        "body": "使用增长驱动关系图、证据矩阵和受众分支路径，正文保持可折叠并提供逐字稿视图。",
                    },
                ),
                affected_ids=(),
                uncertainties=("最终数据图形取决于资料 Agent 的数据输出。",),
                quality_checks=("信息层级清晰", "可由 HTML/CSS/JS 实现", "避免装饰性动效"),
                next_action="待结构批准后生成可验证的 HTML 模块。",
            ),
            "creative": AgentDelivery(
                agent="creative",
                summary="用“增长操作系统升级”统一稳健叙事与突破表达。",
                outputs=(
                    {
                        "kind": "creative_direction",
                        "title": "创意方向",
                        "body": "稳健路线强调增长驱动迁移；突破路线把企业比作正在升级的操作系统，以能力模块解释增长。",
                    },
                ),
                affected_ids=(),
                uncertainties=("突破路线需要根据受众风险偏好选择强度。",),
                quality_checks=("创意服务目标", "同时提供稳健与突破路线", "具备执行路径"),
                next_action="由总控协调内容与视觉 Agent 选择表达强度。",
            ),
        }
        if role not in deliveries:
            raise KeyError(f"Unknown agent role: {role}")
        return deliveries[role]


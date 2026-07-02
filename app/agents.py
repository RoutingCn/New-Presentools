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
        professional = _professional_delivery(role, title, audience)
        if professional:
            return professional
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


def _professional_delivery(role: str, title: str, audience: str) -> AgentDelivery | None:
    bodies = {
        "content": (
            "内容主线应从概念澄清开始，把主题界定为一个需要被重新组织的表达系统，而不是若干页面的堆叠。"
            f"面对{audience}，首先要解释“{title}”解决的不是形式问题，而是内容关系、判断顺序和行动线索如何被看见的问题。",
            "结构关系应采用“问题出现、旧工具失效、新范式成立、落地路径展开”的递进方式。"
            "每一层都要回答上一层留下的疑问，并把反方担心纳入论证，例如学习成本、协作习惯和交付稳定性都需要被正面处理。",
            "可以用一个团队准备季度汇报的例子说明：传统方式会把时间消耗在排版和页码调整上，而 HTML 方式让证据、脚本、跳转和版本锁定围绕同一个内容结构生长。这个例子能让受众立刻理解效率问题背后的结构问题。"
        ),
        "research": (
            "资料判断要先建立证据分层：可直接验证的事实、来自材料的解释、需要进一步调查的假设必须分开标注。"
            "这样总控 agent 才不会把未经核实的判断写成结论，也不会让展示内容显得像未经编辑的资料拼贴。",
            "资料关系应围绕来源、口径、时间和适用范围组织。互联网检索适合补充公开趋势和案例，指定资料目录适合承载内部文档、过往报告和项目素材，两者要互相校验而不是互相替代。",
            "例如分析一个行业主题时，资料 agent 应同时列出政策原文、企业案例、数据口径和缺口清单；如果没有可靠数据，就明确写出需要补证的位置，而不是用模糊形容词撑起结论。"
        ),
        "visual": (
            "视觉概念不应追求单页炫技，而应服务内容关系的显形。页面需要让受众一眼看见主判断、支撑证据、反方张力和下一步行动，视觉层级必须服从论证层级，并把复杂信息整理成可扫描、可停留、可跳转的表达秩序。",
            "视觉关系可以采用左侧结构导航、中央内容节点、右侧过程记忆与修改意见的三栏工作台，在最终 HTML 中再转化为适合演示的章节、锚点、证据卡和聚焦视图。工作台与成品页之间要有清楚映射，避免设计和内容脱节。",
            "例如在生成 HTML 时，可以把核心概念做成第一屏的稳定锚点，把关系链做成可滚动章节，把例子做成可展开案例；这样页面效果来自信息组织，而不是孤立动画。听众看到的是论证逐层展开，而不是模板堆砌。"
        ),
        "creative": (
            "创意概念应把产品表达为“演示的操作系统”，而不是“更会做 PPT 的工具”。这个隐喻能把 agent、资料、结构、逐字稿和 HTML 锁定统一到一个更有穿透力的叙事里。",
            "创意关系要处理传统习惯与新工具之间的心理距离：先承认 PPT 的普及和惯性，再指出真正痛点是内容关系被页面格式压扁，最后给出 HTML + agent 的新秩序。",
            "例如可以设计一条年轻但稳重的表达线：从一份被反复改乱的汇报开始，逐步展示 agent 如何保留讨论痕迹、整理概念关系、生成讲述稿，并把成果锁定成可跳转的网页。这个故事既有冲突，也能自然引出产品价值。"
        ),
    }
    if role not in bodies:
        return None
    concept, relationship, example = bodies[role]
    titles = {
        "content": ("概念定义：演示不是页面集合", "结构关系：从痛点到范式", "例子：季度汇报的重组"),
        "research": ("概念定义：证据分层", "资料关系：双源校验", "例子：行业主题调查"),
        "visual": ("概念定义：让关系可见", "视觉关系：工作台到演示页", "例子：章节与案例展开"),
        "creative": ("概念定义：演示操作系统", "创意关系：惯性到新秩序", "例子：从混乱汇报到网页成果"),
    }[role]
    return AgentDelivery(
        agent=role,
        summary=f"{role} agent 已围绕《{title}》形成概念、关系和例子的完整结构。",
        outputs=(
            {"kind": "concept", "title": titles[0], "body": concept},
            {"kind": "relationship", "title": titles[1], "body": relationship},
            {"kind": "example", "title": titles[2], "body": example},
        ),
        affected_ids=(),
        uncertainties=("仍需结合具体主题补充行业资料、真实案例和受众语境。",),
        quality_checks=("概念清楚", "关系自洽", "包含例子", "语言完整"),
        next_action="由总控 agent 合并四类输出，形成可审阅、可修改的内容结构。",
    )


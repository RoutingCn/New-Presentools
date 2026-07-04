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
        if role == "script":
            return self._script_delivery(title, audience)
        return self._agent_delivery(role, title, audience, context)

    def _agent_delivery(
        self,
        role: str,
        title: str,
        audience: str,
        context: dict[str, Any],
    ) -> AgentDelivery:
        bodies = {
            "content": (
                f"内容主线应从概念澄清开始，把「{title}」界定为一个需要被重新组织的表达系统，"
                f"而不是若干页面的堆叠。面对{audience}，首先要解释「{title}」解决的不是形式问题，"
                "而是内容关系、判断顺序和行动线索如何被看见的问题。",
                "结构关系应采用「问题出现 → 旧工具失效 → 新范式成立 → 落地路径展开」的递进方式。"
                "每一层都要回答上一层留下的疑问，并把反方担心纳入论证，例如学习成本、协作习惯和"
                "交付稳定性都需要被正面处理。",
                "可以用一个团队准备季度汇报的例子说明：传统方式会把时间消耗在排版和页码调整上，"
                "而 HTML 方式让证据、脚本、跳转和版本锁定围绕同一个内容结构生长。"
                "这个例子能让受众立刻理解效率问题背后的结构问题。",
            ),
            "research": (
                "资料判断要先建立证据分层：可直接验证的事实、来自材料的解释、"
                "需要进一步调查的假设必须分开标注。这样总控 agent 才不会把未经核实的判断写成结论，"
                "也不会让展示内容显得像未经编辑的资料拼贴。",
                "资料关系应围绕来源、口径、时间和适用范围组织。互联网检索适合补充公开趋势和案例，"
                "指定资料目录适合承载内部文档、过往报告和项目素材，两者要互相校验而不是互相替代。",
                f"例如分析「{title}」时，资料 agent 应同时列出政策原文、企业案例、数据口径和缺口清单；"
                "如果没有可靠数据，就明确写出需要补证的位置，而不是用模糊形容词撑起结论。",
            ),
            "visual": (
                "视觉概念不应追求单页炫技，而应服务内容关系的显形。页面需要让受众一眼看见主判断、"
                "支撑证据、反方张力和下一步行动，视觉层级必须服从论证层级，"
                "并把复杂信息整理成可扫描、可停留、可跳转的表达秩序。",
                "视觉关系可以采用左侧结构导航、中央内容节点、右侧过程记忆与修改意见的三栏工作台，"
                "在最终 HTML 中再转化为适合演示的章节、锚点、证据卡和聚焦视图。"
                "工作台与成品页之间要有清楚映射，避免设计和内容脱节。",
                "例如在生成 HTML 时，可以把核心概念做成第一屏的稳定锚点，把关系链做成可滚动章节，"
                "把例子做成可展开案例；这样页面效果来自信息组织，而不是孤立动画。"
                "听众看到的是论证逐层展开，而不是模板堆砌。",
            ),
            "creative": (
                "创意概念应把产品表达为「演示的操作系统」，而不是「更会做 PPT 的工具」。"
                "这个隐喻能把 agent、资料、结构、逐字稿和 HTML 锁定统一到一个更有穿透力的叙事里。",
                "创意关系要处理传统习惯与新工具之间的心理距离：先承认 PPT 的普及和惯性，"
                "再指出真正痛点是内容关系被页面格式压扁，最后给出 HTML + agent 的新秩序。",
                "例如可以设计一条年轻但稳重的表达线：从一份被反复改乱的汇报开始，"
                "逐步展示 agent 如何保留讨论痕迹、整理概念关系、生成讲述稿，"
                "并把成果锁定成可跳转的网页。这个故事既有冲突，也能自然引出产品价值。",
            ),
        }
        concept, relationship, example = bodies[role]
        titles = {
            "content": ("概念定义：演示不是页面集合", "结构关系：从痛点到范式", "例子：季度汇报的重组"),
            "research": ("概念定义：证据分层", "资料关系：双源校验", f"例子：{title}的调研"),
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

    def _script_delivery(
        self,
        title: str,
        audience: str,
    ) -> AgentDelivery:
        outputs = (
            {
                "kind": "script_intro",
                "title": "开场与问题引入",
                "body": (
                    f"感谢各位今天的时间。今天我们要讨论的主题是《{title}》。"
                    f"在座的各位——{audience}——每天都在面对这个问题带来的挑战和机会。"
                    "但在深入之前，我想先请大家思考一个问题：我们是否在用旧工具解决新问题？\n"
                    "今天我带来的不是一个结论，而是一套新的思考方式。"
                ),
            },
            {
                "kind": "script_definition",
                "title": "核心概念定义",
                "body": (
                    f"那么，《{title}》到底意味着什么？在深入细节之前，"
                    "我想先花两分钟厘清这个概念。很多人把它理解为页面、工具或格式问题，"
                    "但真正重要的不是呈现形式，而是内容之间的逻辑关系如何被看见、被理解、被记住。\n"
                    "一旦关系清楚了，听众就不需要你反复解释——他们自己能看出推理的走向。"
                ),
            },
            {
                "kind": "script_body",
                "title": "论证展开",
                "body": (
                    "下面我们来看三个关键判断。\n"
                    "第一，旧工具之所以失效，不是因为功能不够，而是因为它们把内容关系压扁成了平面列表。"
                    "这也解释了为什么听众经常走神——不是讲得不好，而是关系看不见。\n"
                    "第二，新的生产方式让内容结构和展示形式同时生长。"
                    "不用先写完再排版，也不用因为排版要求而删改论证。\n"
                    "第三，锁定版本和可修订版本可以共存。"
                    "这意味着你可以为一个重要的董事会生成一个不可篡改的版本，"
                    "同时在另一个版本里继续迭代观点和证据。"
                ),
            },
            {
                "kind": "script_example",
                "title": "说明例子",
                "body": (
                    "举个例子：假设你要为一个季度的战略回顾做汇报。传统流程是——"
                    "写提纲、填内容、调格式、加图表、改字号、对页码，然后发给领导。"
                    "领导回一个字：改。你就重新从第二步开始。\n"
                    "而新的流程是：提纲就是内容节点，内容节点直接产出一版 HTML 预览，"
                    "修改意见针对具体的论点而不是「第五页标题大一点」，"
                    "所有改动都有记录，锁定版不动，继续改的版本走新的分支。\n"
                    "你的时间从调格式回到写东西。"
                ),
            },
            {
                "kind": "script_transition",
                "title": "转场与总结",
                "body": (
                    "最后，我想回到一开始的问题：我们是不是在用旧工具解决新问题？\n"
                    "答案是：是的。但好消息是，新工具已经在手边了。"
                    "它对我们的要求不是学更多功能，而是换一种看待内容的方式——"
                    "把演示当作一个有机生长的信息系统，而不是一个需要反复手调的静态文件。\n"
                    "谢谢各位，接下来我们可以深入讨论任何一部分。"
                ),
            },
        )
        return AgentDelivery(
            agent="script",
            summary=f"围绕《{title}》，面向{audience}，输出从开场到总结的完整讲述稿。",
            outputs=outputs,
            affected_ids=(),
            uncertainties=(
                "逐字稿需要根据实际内容结构做针对性调整，当前为通用模板。",
                "语气强度需根据受众偏好进一步选择。",
            ),
            quality_checks=(
                "结构完整（开场→定义→论证→例子→总结）",
                "语言适合口头表达",
                "转场自然不跳脱",
                "例子具体可用",
            ),
            next_action="待全量内容结构批准后，基于实际节点生成定制化逐字稿。",
        )

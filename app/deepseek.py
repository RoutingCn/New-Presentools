from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .agents import AgentDelivery
from .provider_config import ProviderConfig


ROLE_INSTRUCTIONS = {
    "content": "你是顶级标准的成熟内容总编辑，负责概念定义、论证结构、反方观点、叙事层次和语言质量。",
    "research": "你是顶级标准的调查员和数据分析师，负责事实边界、证据链、数据口径、案例线索和风险提示。",
    "visual": "你是顶级标准的视觉设计师和前端工程师，负责信息架构、页面关系、交互层次和可实现的 HTML/CSS/JS 表达。",
    "creative": "你是顶级标准的创意总监，同时保持年轻创意师的敏锐，负责叙事角度、隐喻系统、突破性表达和可执行创意。",
    "script": "你是顶级标准的演讲撰写人和表达教练，负责将内容结构转化为自然流畅的讲述稿，包含开场、过渡、例子和收束，语气适合口头表达，语言通顺有节奏感。",
}

SCRIPT_OUTPUT_CONTRACT = (
    "必须按顶级标准输出。script agent 至少给出 5 个 outputs，覆盖开场引入、概念定义、论证展开、"
    "说明例子和转场总结。每个 output 的 body 必须是可直接口头讲述的完整段落，"
    "语言自然流畅，节奏分明，适合演讲场景。不得输出空泛口号或短句列表。"
    "逐字稿必须独立于 HTML 展示内容，可以单独下载和使用。"
)

PROFESSIONAL_OUTPUT_CONTRACT = (
    "必须按顶级标准输出。每个 agent 至少给出 3 个 outputs，覆盖 concept、relationship、example "
    "或与角色高度相关的等价模块。每个 output 的 body 必须是完整段落，说明概念、关系、例子、"
    "边界和表达意图，保证逻辑自洽，语言通顺优美，不能只写口号、短句或空泛建议。"
    "同一批 outputs 不得重复标题，不得重复或改写同质内容。"
    "输出要能被总控 agent 直接合并为完整的内容结构。"
)

DELIVERY_FIELDS = (
    "agent", "summary", "outputs", "affected_ids", "uncertainties",
    "quality_checks", "next_action",
)


class HttpTransport(Protocol):
    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        ...


class UrllibTransport:
    def __call__(
        self,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        timeout: float,
    ) -> dict[str, Any]:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code in (401, 403):
                raise ValueError("DeepSeek authentication failed") from None
            if error.code == 429:
                raise ValueError("DeepSeek rate limit reached") from None
            raise ValueError(f"DeepSeek request failed with status {error.code}") from None
        except TimeoutError:
            raise ValueError("DeepSeek request timed out") from None
        except URLError:
            raise ValueError("DeepSeek network unavailable") from None


class DeepSeekProvider:
    def __init__(
        self,
        config: ProviderConfig,
        transport: HttpTransport | None = None,
    ):
        if not config.deepseek_enabled:
            raise ValueError("DeepSeek provider requires DEEPSEEK_API_KEY")
        self.config = config
        self.transport = transport or UrllibTransport()

    def run(
        self,
        role: str,
        contract: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentDelivery:
        if role not in ROLE_INSTRUCTIONS:
            raise KeyError(f"Unknown agent role: {role}")
        response = self.transport(
            f"{self.config.base_url}/chat/completions",
            {
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
            },
            {
                "model": self.config.model,
                "messages": _build_messages(role, contract, context),
                "response_format": {"type": "json_object"},
                "max_tokens": 3000,
            },
            self.config.timeout_seconds,
        )
        try:
            return _parse_delivery(role, response)
        except ValueError as error:
            response = self.transport(
                f"{self.config.base_url}/chat/completions",
                {
                    "Authorization": f"Bearer {self.config.api_key}",
                    "Content-Type": "application/json",
                },
                {
                    "model": self.config.model,
                    "messages": _build_messages(role, contract, context)
                    + [_repair_message(error)],
                    "response_format": {"type": "json_object"},
                    "max_tokens": 3000,
                },
                self.config.timeout_seconds,
            )
            return _parse_delivery(role, response)


def _repair_message(error: ValueError) -> dict[str, str]:
    return {
        "role": "user",
        "content": (
            "Your previous delivery was rejected: "
            f"{error}. Return one complete JSON object with agent, summary, "
            "a non-empty outputs array, affected_ids, uncertainties, "
            "quality_checks, and next_action. Do not use Markdown."
        ),
    }


def _build_messages(
    role: str,
    contract: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    is_script = role == "script"
    if is_script:
        example = {
            "agent": "script",
            "summary": "围绕主题和受众形成的完整讲述稿结构",
            "outputs": [
                {
                    "kind": "script_intro",
                    "title": "开场与问题引入",
                    "body": "用完整的演讲段落引入主题，建立与受众的连接，明确要解决的问题。",
                },
                {
                    "kind": "script_definition",
                    "title": "核心概念定义",
                    "body": "用口语化的方式解释核心概念，让听众在进入细节前建立基本理解。",
                },
                {
                    "kind": "script_body",
                    "title": "论证展开",
                    "body": "逐层展开关键判断，每层回答上一层留下问题，保持叙事节奏。",
                },
                {
                    "kind": "script_example",
                    "title": "说明例子",
                    "body": "给出具体、可感知的例子，让抽象判断落到听众经验里。",
                },
                {
                    "kind": "script_transition",
                    "title": "转场与总结",
                    "body": "自然收束论证，回到开头的主题，给出清晰结论和下一步讨论的钩子。",
                },
            ],
            "affected_ids": [],
            "uncertainties": ["尚待确认的受众偏好和语气强度"],
            "quality_checks": ["结构完整", "语言适合口语", "转场自然", "例子具体"],
            "next_action": "待内容结构确定后进一步定制",
        }
        output_contract = SCRIPT_OUTPUT_CONTRACT
    else:
        example = {
            "agent": role,
            "summary": "本角色形成的专业判断和结构贡献",
            "outputs": [
                {
                    "kind": "concept",
                    "title": "核心概念",
                    "body": "用完整段落定义关键概念，说明它为什么重要，以及它和主题之间的关系。",
                },
                {
                    "kind": "relationship",
                    "title": "关系结构",
                    "body": "用完整段落说明多个概念、证据或行动之间的因果、递进或张力关系。",
                },
                {
                    "kind": "example",
                    "title": "说明例子",
                    "body": "用完整段落给出可以帮助受众理解的例子，并说明例子对应的判断边界。",
                },
            ],
            "affected_ids": [],
            "uncertainties": ["尚待确认的问题"],
            "quality_checks": ["已执行的质量检查"],
            "next_action": "建议的下一步",
        }
        output_contract = PROFESSIONAL_OUTPUT_CONTRACT
    system = (
        f"{ROLE_INSTRUCTIONS[role]} {output_contract} "
        "只输出合法 JSON，不要使用 Markdown。"
        "不得虚构资料、数据或已经完成的工具操作。"
        f"输出结构示例：{json.dumps(example, ensure_ascii=False)}"
    )
    user = json.dumps(
        {"task_contract": contract, "project_context": context},
        ensure_ascii=False,
        default=str,
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


def _parse_delivery(role: str, response: dict[str, Any]) -> AgentDelivery:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("DeepSeek returned an invalid response envelope") from None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("DeepSeek returned empty content")
    try:
        value = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("DeepSeek returned invalid JSON") from None
    if any(field not in value for field in DELIVERY_FIELDS):
        raise ValueError("DeepSeek delivery missing fields")
    if value["agent"] != role:
        raise ValueError("DeepSeek delivery role mismatch")
    if not isinstance(value["outputs"], list) or not value["outputs"]:
        raise ValueError("DeepSeek delivery requires non-empty outputs")
    return AgentDelivery(
        agent=value["agent"],
        summary=value["summary"],
        outputs=tuple(value["outputs"]),
        affected_ids=tuple(value["affected_ids"]),
        uncertainties=tuple(value["uncertainties"]),
        quality_checks=tuple(value["quality_checks"]),
        next_action=value["next_action"],
    )

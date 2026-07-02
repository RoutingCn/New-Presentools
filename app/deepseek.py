from __future__ import annotations

import json
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .agents import AgentDelivery
from .provider_config import ProviderConfig


ROLE_INSTRUCTIONS = {
    "content": "你是成熟的内容编辑，负责论点、结构、反方观点和表达质量。",
    "research": "你是调查员和数据分析师，区分事实、推断与证据缺口，不虚构来源。",
    "visual": "你是视觉设计师和前端工程师，提出可由 HTML/CSS/JS 实现的信息设计。",
    "creative": "你兼具创意总监的视野和年轻创意师的敏锐，提供可执行的突破性方向。",
}

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
        return _parse_delivery(role, response)


def _build_messages(
    role: str,
    contract: dict[str, Any],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    example = {
        "agent": role,
        "summary": "本角色的主要结论",
        "outputs": [{"kind": "claim", "title": "标题", "body": "正文"}],
        "affected_ids": [],
        "uncertainties": ["尚待确认的问题"],
        "quality_checks": ["已执行的质量检查"],
        "next_action": "建议的下一步",
    }
    system = (
        f"{ROLE_INSTRUCTIONS[role]} 只输出合法 JSON，不要使用 Markdown。"
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

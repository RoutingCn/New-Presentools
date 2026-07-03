from __future__ import annotations

import json
import re
from html import escape
from typing import Protocol

from .deepseek import HttpTransport, UrllibTransport
from .domain import ContentNode, ProjectState
from .provider_config import ProviderConfig


class HtmlProvider(Protocol):
    def render(self, state: ProjectState, nodes: tuple[ContentNode, ...]) -> str:
        ...


class LocalHtmlProvider:
    def render(self, state: ProjectState, nodes: tuple[ContentNode, ...]) -> str:
        articles = "\n".join(
            (
                f'<article class="slide" id="{escape(node.id)}">'
                f"<small>{escape(node.kind)}</small>"
                f"<h2>{escape(node.title)}</h2>"
                f"<p>{escape(node.body).replace(chr(10), '<br>')}</p>"
                "</article>"
            )
            for node in nodes
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


class ArkHtmlProvider:
    def __init__(
        self,
        config: ProviderConfig,
        transport: HttpTransport | None = None,
    ):
        if not config.ark_html_enabled:
            raise ValueError("Ark HTML provider requires ARK_API_KEY")
        self.config = config
        self.transport = transport or UrllibTransport()

    def render(self, state: ProjectState, nodes: tuple[ContentNode, ...]) -> str:
        try:
            response = self.transport(
                f"{self.config.ark_base_url}/chat/completions",
                {
                    "Authorization": f"Bearer {self.config.ark_api_key}",
                    "Content-Type": "application/json",
                },
                {
                    "model": self.config.ark_model,
                    "messages": _build_messages(state, nodes),
                    "max_tokens": 6000,
                },
                self.config.ark_timeout_seconds,
            )
        except ValueError as error:
            raise ValueError(_ark_error_message(str(error))) from None
        return _parse_html(response)


def _build_messages(
    state: ProjectState,
    nodes: tuple[ContentNode, ...],
) -> list[dict[str, str]]:
    payload = {
        "title": state.title,
        "audience": state.audience,
        "nodes": [
            {
                "id": node.id,
                "kind": node.kind,
                "title": node.title,
                "body": node.body,
            }
            for node in nodes
        ],
    }
    system = (
        "你是顶级视觉设计师和前端工程师。请把给定内容结构生成一个单文件 HTML 演示成品。"
        "只输出完整 HTML，不要 Markdown，不要解释。"
        "HTML 必须自包含 CSS，结构清晰，适合浏览器直接打开。"
        "不要加入逐字稿，不要虚构外部数据。"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def _parse_html(response: dict) -> str:
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("Ark HTML provider returned an invalid response envelope") from None
    if not isinstance(content, str) or not content.strip():
        raise ValueError("Ark HTML provider returned empty content")
    return _normalize_html(_strip_fence(content.strip()))


def _ark_error_message(message: str) -> str:
    normalized = message.replace("DeepSeek", "Ark HTML provider")
    if "status 404" in normalized:
        normalized += (
            ". Check the HTML API base URL and model or endpoint id in the HTML API panel."
        )
    return normalized


def _strip_fence(content: str) -> str:
    match = re.fullmatch(r"```(?:html)?\s*(.*?)\s*```", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    return content


def _normalize_html(content: str) -> str:
    match = re.search(r"<!doctype html>.*", content, re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(0).strip()
    match = re.search(r"<html[\s\S]*", content, re.IGNORECASE)
    if match:
        return "<!doctype html>\n" + match.group(0).strip()
    return (
        "<!doctype html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>HTML Presentation</title>\n"
        "<style>\n"
        "body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif;background:#f6f7f9;color:#15171a;}\n"
        "main{max-width:1080px;margin:0 auto;padding:48px 24px;}\n"
        "section,article{background:white;border:1px solid #d7dce2;border-left:5px solid #15171a;margin:18px 0;padding:24px;}\n"
        "h1,h2,h3{line-height:1.25;}p,li{font-size:18px;line-height:1.75;}\n"
        "</style>\n"
        "</head>\n"
        "<body><main>\n"
        f"{content}\n"
        "</main></body>\n"
        "</html>\n"
    )

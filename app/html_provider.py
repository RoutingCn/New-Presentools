from __future__ import annotations

from html import escape
from typing import Protocol

from .domain import ContentNode, ProjectState


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

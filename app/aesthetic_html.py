from __future__ import annotations

import re
from html import escape
from typing import Any

from .domain import ContentNode, ProjectState


PARADIGMS: dict[str, dict[str, str]] = {
    "swiss": {
        "name": "Swiss Modern",
        "bg": "#f4f4f2",
        "paper": "#ffffff",
        "ink": "#202124",
        "muted": "#666a73",
        "line": "#d9d9d4",
        "accent": "#b8504a",
        "accent2": "#6f7f9f",
        "font": "Arial, 'Microsoft YaHei', sans-serif",
    },
    "editorial": {
        "name": "Editorial Classic",
        "bg": "#f7f3eb",
        "paper": "#fffaf1",
        "ink": "#2c2621",
        "muted": "#78695f",
        "line": "#d8cbb8",
        "accent": "#7a5c4a",
        "accent2": "#b08c62",
        "font": "Georgia, 'Microsoft YaHei', serif",
    },
    "dark": {
        "name": "Dark Tech",
        "bg": "#14151d",
        "paper": "#1d1f2a",
        "ink": "#f4f5f8",
        "muted": "#b7bcc8",
        "line": "#303442",
        "accent": "#5a9e78",
        "accent2": "#7e74b4",
        "font": "Arial, 'Microsoft YaHei', sans-serif",
    },
    "brutal": {
        "name": "Neo Brutalist",
        "bg": "#e9dfca",
        "paper": "#ffffff",
        "ink": "#242428",
        "muted": "#4e5665",
        "line": "#242428",
        "accent": "#cfa8a6",
        "accent2": "#7078a4",
        "font": "Arial, 'Microsoft YaHei', sans-serif",
    },
}


def nodes_to_markdown(
    title: str,
    audience: str,
    nodes: tuple[ContentNode, ...],
) -> str:
    lines = [f"# {title.strip() or 'Untitled'}", ""]
    if audience.strip():
        lines.extend([f"> Audience: {audience.strip()}", ""])
    for node in nodes:
        if node.kind == "script":
            continue
        lines.extend([f"## {node.title.strip() or node.kind}", ""])
        body = node.body.strip()
        if body:
            lines.extend([body, ""])
    return "\n".join(lines).strip() + "\n"


class AestheticHtmlProvider:
    def __init__(self, paradigm: str = "swiss"):
        if paradigm not in PARADIGMS:
            raise ValueError(f"Unsupported aesthetic paradigm: {paradigm}")
        self.paradigm = paradigm

    def render(self, state: ProjectState, nodes: tuple[ContentNode, ...]) -> str:
        markdown = nodes_to_markdown(state.title, state.audience, nodes)
        return render_markdown(markdown, self.paradigm)


def render_markdown(markdown: str, paradigm: str = "swiss") -> str:
    if paradigm not in PARADIGMS:
        raise ValueError(f"Unsupported aesthetic paradigm: {paradigm}")
    title = _extract_title(markdown)
    headings = _headings(markdown)
    toc = _build_toc(headings)
    body = _render_sections(markdown)
    theme = PARADIGMS[paradigm]
    return (
        "<!doctype html>\n"
        f'<html lang="zh-CN" data-paradigm="{escape(paradigm)}">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>{_css(theme)}</style>\n"
        "</head>\n"
        "<body>\n"
        f'<nav id="outline" aria-label="大纲"><strong>{escape(theme["name"])}</strong>{toc}</nav>\n'
        '<button id="outline-toggle" type="button" aria-label="折叠大纲">☰</button>\n'
        f'<main id="content">{body}<footer>{escape(theme["name"])}</footer></main>\n'
        f"<script>{_shared_js()}</script>\n"
        "</body>\n"
        "</html>\n"
    )


def _extract_title(markdown: str) -> str:
    match = re.search(r"^#\s+(.+)$", markdown, re.MULTILINE)
    return match.group(1).strip() if match else "HTML Presentation"


def _headings(markdown: str) -> list[tuple[int, str, str]]:
    result: list[tuple[int, str, str]] = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{1,3})\s+(.+)$", line)
        if match:
            text = match.group(2).strip()
            result.append((len(match.group(1)), text, _slug(text)))
    return result


def _build_toc(headings: list[tuple[int, str, str]]) -> str:
    items = [
        f'<li class="level-{level}"><a href="#{escape(slug)}">{escape(text)}</a></li>'
        for level, text, slug in headings
        if level >= 2
    ]
    if not items:
        return ""
    return '<ol class="outline-tree">' + "".join(items) + "</ol>"


def _render_sections(markdown: str) -> str:
    lines = markdown.splitlines()
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    current_title = ""
    current_lines: list[str] = []
    for line in lines:
        match = re.match(r"^##\s+(.+)$", line)
        if match:
            if current_title:
                sections.append((current_title, current_lines))
            else:
                intro = current_lines
            current_title = match.group(1).strip()
            current_lines = []
            continue
        if re.match(r"^#\s+.+$", line):
            continue
        current_lines.append(line)
    if current_title:
        sections.append((current_title, current_lines))
    elif current_lines:
        intro = current_lines

    html: list[str] = []
    title = _extract_title(markdown)
    hero_blocks = _render_blocks(intro)
    html.append(
        f'<section id="{escape(_slug(title))}" class="section section-hero">'
        f'<div class="section-inner"><p class="eyebrow">HTML Presentation</p>'
        f"<h1>{escape(title)}</h1>{hero_blocks}</div></section>"
    )
    classes = ("section-alt", "section-paper", "section-accent")
    for index, (section_title, section_lines) in enumerate(sections):
        class_name = classes[index % len(classes)]
        html.append(
            f'<section id="{escape(_slug(section_title))}" class="section {class_name}">'
            f'<div class="section-inner"><h2>{escape(section_title)}</h2>'
            f"{_render_blocks(section_lines)}</div></section>"
        )
    return "".join(html)


def _render_blocks(lines: list[str]) -> str:
    html: list[str] = []
    paragraph: list[str] = []
    i = 0

    def flush_paragraph() -> None:
        if paragraph:
            text = " ".join(item.strip() for item in paragraph if item.strip())
            if text:
                html.append(f"<p>{_inline(text)}</p>")
            paragraph.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        if not line.strip():
            flush_paragraph()
            i += 1
            continue
        if _is_table_start(lines, i):
            flush_paragraph()
            table_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            html.append(_render_table(table_lines))
            continue
        if re.match(r"^\s*[-*]\s+", line):
            flush_paragraph()
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*]\s+", "", lines[i]).strip())
                i += 1
            html.append(_render_list(items))
            continue
        if line.startswith(">"):
            flush_paragraph()
            quote = line.lstrip("> ").strip()
            html.append(f"<blockquote>{_inline(quote)}</blockquote>")
            i += 1
            continue
        paragraph.append(line)
        i += 1
    flush_paragraph()
    return "".join(html)


def _is_table_start(lines: list[str], index: int) -> bool:
    return (
        index + 1 < len(lines)
        and lines[index].strip().startswith("|")
        and re.match(r"^\s*\|?[\s:-]+\|[\s|:-]+$", lines[index + 1]) is not None
    )


def _render_table(lines: list[str]) -> str:
    rows = [_split_table_row(line) for line in lines if line.strip().startswith("|")]
    if len(rows) < 2:
        return ""
    header = rows[0]
    body_rows = rows[2:]
    numeric_count = sum(
        1
        for row in body_rows
        for cell in row
        if re.search(r"\d+[%％]?|\d[\d,.]*\s*(万|亿|k|m)", cell, re.IGNORECASE)
    )
    if body_rows and numeric_count >= len(body_rows):
        cards = []
        for row in body_rows:
            label = escape(row[0]) if row else ""
            value = escape(row[1]) if len(row) > 1 else ""
            detail = " / ".join(escape(cell) for cell in row[2:])
            cards.append(
                '<article class="stat-card">'
                f'<span class="stat-label">{label}</span>'
                f'<strong class="stat-value">{value}</strong>'
                f'<small>{detail}</small>'
                "</article>"
            )
        return '<div class="stat-card-row">' + "".join(cards) + "</div>"
    head = "".join(f"<th>{escape(cell)}</th>" for cell in header)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>"
        for row in body_rows
    )
    return f'<table class="data-table"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def _split_table_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def _render_list(items: list[str]) -> str:
    if len(items) >= 3 and all(re.match(r"^\*\*\d{4}.*?\*\*", item) for item in items):
        rendered = "".join(
            f'<article class="timeline-item"><span></span><p>{_inline(item)}</p></article>'
            for item in items
        )
        return f'<div class="timeline">{rendered}</div>'
    return "<ul>" + "".join(f"<li>{_inline(item)}</li>" for item in items) + "</ul>"


def _inline(text: str) -> str:
    escaped = escape(text)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"`(.+?)`", r"<code>\1</code>", escaped)
    return escaped


def _slug(value: str) -> str:
    slug = re.sub(r"[^\w\u4e00-\u9fff]+", "-", value.lower(), flags=re.UNICODE)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug or "section"


def _css(theme: dict[str, str]) -> str:
    css = """
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:__BG__;color:__INK__;font-family:__FONT__;display:flex;min-height:100vh}a{color:inherit}
#outline{width:260px;min-width:260px;height:100vh;position:sticky;top:0;padding:34px 22px;background:__PAPER__;border-right:1px solid __LINE__;overflow:auto}
#outline strong{display:block;margin-bottom:18px;font-size:14px;letter-spacing:.02em}.outline-tree{list-style:none;margin:0;padding:0}.outline-tree li{margin:0 0 5px}.outline-tree a{display:block;padding:7px 8px;border-radius:6px;text-decoration:none;color:__MUTED__;font-size:13px}
.outline-tree a:hover,.outline-tree a.active{background:__BG__;color:__ACCENT__}
#outline-toggle{position:fixed;left:242px;top:14px;width:30px;height:30px;border:1px solid __LINE__;background:__PAPER__;color:__MUTED__;border-radius:999px;cursor:pointer}
#outline.collapsed{width:44px;min-width:44px;padding-left:8px;padding-right:8px}#outline.collapsed strong,#outline.collapsed .outline-tree{display:none}#outline.collapsed~#outline-toggle{left:28px}
#content{flex:1;min-width:0}.section{min-height:72vh;padding:56px clamp(24px,6vw,84px);border-bottom:1px solid __LINE__}.section-inner{max-width:980px;margin:0 auto}
.section-hero{display:flex;align-items:center;background:__PAPER__}.section-alt{background:__BG__}.section-paper{background:__PAPER__}.section-accent{background:linear-gradient(90deg,__PAPER__,__SOFT__)}
.eyebrow{margin:0 0 18px;color:__ACCENT__;font-size:12px;text-transform:uppercase;letter-spacing:.12em;font-weight:700}
h1{font-size:clamp(38px,6vw,74px);line-height:1.02;margin:0 0 24px;letter-spacing:0}h2{font-size:clamp(28px,4vw,46px);line-height:1.12;margin:0 0 22px;letter-spacing:0}
p,li{font-size:18px;line-height:1.75;color:__MUTED__;max-width:760px}strong{color:__INK__}blockquote{margin:28px 0;padding:18px 22px;border-left:5px solid __ACCENT__;background:__PAPER__;color:__MUTED__}ul{padding-left:22px}
.data-table{width:100%;border-collapse:collapse;margin:22px 0;background:__PAPER__}.data-table th,.data-table td{padding:12px 14px;text-align:left;border-bottom:1px solid __LINE__}.data-table th{font-size:12px;text-transform:uppercase;color:__ACCENT__}
.stat-card-row{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:14px;margin:26px 0}.stat-card{padding:22px 18px;background:__PAPER__;border:1px solid __LINE__;border-top:5px solid __ACCENT__}.stat-label{display:block;color:__MUTED__;font-size:13px;margin-bottom:8px}.stat-value{display:block;font-size:32px;color:__INK__}.stat-card small{display:block;margin-top:8px;color:__MUTED__}
.timeline{position:relative;margin:24px 0;padding-left:24px;border-left:2px solid __ACCENT__}.timeline-item{position:relative;margin:0 0 18px}.timeline-item span{position:absolute;left:-31px;top:8px;width:12px;height:12px;border-radius:50%;background:__ACCENT__}
footer{padding:28px 40px;color:__MUTED__;font-size:12px;text-align:center}@media(max-width:780px){body{display:block}#outline,#outline-toggle{display:none}.section{min-height:auto;padding:42px 24px}p,li{font-size:16px}}
"""
    replacements = {
        "__BG__": theme["bg"],
        "__PAPER__": theme["paper"],
        "__INK__": theme["ink"],
        "__MUTED__": theme["muted"],
        "__LINE__": theme["line"],
        "__ACCENT__": theme["accent"],
        "__SOFT__": theme["bg"],
        "__FONT__": theme["font"],
    }
    for key, value in replacements.items():
        css = css.replace(key, value)
    return css


def _shared_js() -> str:
    return """
const outline=document.getElementById('outline');
document.getElementById('outline-toggle')?.addEventListener('click',()=>outline.classList.toggle('collapsed'));
const links=[...document.querySelectorAll('#outline a')];
const sections=[...document.querySelectorAll('section[id]')];
function updateActive(){let current='';for(const section of sections){if(section.getBoundingClientRect().top<=180)current=section.id}links.forEach(link=>link.classList.toggle('active',link.getAttribute('href')==='#'+current))}
document.addEventListener('scroll',updateActive,{passive:true});updateActive();
"""

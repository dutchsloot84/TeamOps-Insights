"""Utilities to convert Atlassian Document Format (ADF) to Markdown."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional


def to_markdown(adf: Optional[Dict[str, Any]]) -> str:
    """Render an ADF document to Markdown."""

    if not isinstance(adf, dict):
        return ""

    content = adf.get("content")
    if not isinstance(content, list):
        return ""

    blocks: List[str] = []
    for node in content:
        rendered = _render_block(node)
        if rendered is None:
            continue
        blocks.append(rendered.rstrip())

    text = "\n\n".join(blocks)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _render_block(node: Dict[str, Any], indent: int = 0) -> Optional[str]:
    node_type = node.get("type")
    if node_type == "paragraph":
        return _render_paragraph(node)
    if node_type == "heading":
        return _render_heading(node)
    if node_type == "bulletList":
        return _render_list(node, indent=indent, ordered=False)
    if node_type == "orderedList":
        order = node.get("attrs", {}).get("order", 1)
        return _render_list(node, indent=indent, ordered=True, start=order)
    if node_type == "codeBlock":
        return _render_code_block(node)
    if node_type == "blockquote":
        return _render_blockquote(node, indent)
    if node_type == "rule":
        return "---"
    if node_type == "hardBreak":
        return ""
    return None


def _render_paragraph(node: Dict[str, Any]) -> str:
    text = _render_inline(node.get("content", []))
    return text.strip()


def _render_heading(node: Dict[str, Any]) -> str:
    level = node.get("attrs", {}).get("level", 1)
    try:
        level = int(level)
    except (TypeError, ValueError):
        level = 1
    level = max(1, min(6, level))
    text = _render_inline(node.get("content", []))
    return f"{'#' * level} {text.strip()}"


def _render_code_block(node: Dict[str, Any]) -> str:
    language = node.get("attrs", {}).get("language")
    code_lines: List[str] = []
    for child in node.get("content", []):
        if child.get("type") == "text":
            code_lines.append(child.get("text", ""))
    code = "".join(code_lines)
    fence = f"```{language}" if language else "```"
    return f"{fence}\n{code}\n```"


def _render_blockquote(node: Dict[str, Any], indent: int) -> str:
    lines: List[str] = []
    for child in node.get("content", []):
        rendered = _render_block(child, indent)
        if not rendered:
            continue
        for line in rendered.splitlines():
            lines.append(f"> {line}" if line else ">")
    return "\n".join(lines)


def _render_list(
    node: Dict[str, Any],
    *,
    indent: int,
    ordered: bool,
    start: int = 1,
) -> str:
    lines: List[str] = []
    items: List[Dict[str, Any]] = node.get("content", [])
    counter = start
    for item in items:
        marker = f"{counter}." if ordered else "-"
        prefix = f"{' ' * indent}{marker} "
        text_parts: List[str] = []
        nested_blocks: List[str] = []
        for child in item.get("content", []):
            child_type = child.get("type")
            if child_type == "paragraph":
                paragraph = _render_inline(child.get("content", []))
                if paragraph:
                    text_parts.append(paragraph.replace("\n", " ").strip())
            elif child_type in {"bulletList", "orderedList"}:
                nested = _render_list(
                    child,
                    indent=indent + 2,
                    ordered=child_type == "orderedList",
                    start=child.get("attrs", {}).get("order", 1),
                )
                if nested:
                    nested_blocks.append(nested)
            else:
                other = _render_block(child, indent=indent + 2)
                if other:
                    text_parts.append(other.strip())
        line = prefix + " ".join(text_parts).strip()
        lines.append(line.rstrip())
        for nested in nested_blocks:
            lines.extend(nested.splitlines())
        if ordered:
            counter += 1
    return "\n".join(lines)


def _render_inline(content: Iterable[Dict[str, Any]]) -> str:
    parts: List[str] = []
    for node in content:
        node_type = node.get("type")
        if node_type == "text":
            text = node.get("text", "")
            for mark in node.get("marks", []):
                text = _apply_mark(text, mark)
            parts.append(text)
        elif node_type == "hardBreak":
            parts.append("\n")
        elif node_type == "paragraph":
            parts.append(_render_paragraph(node))
        elif node_type == "emoji":
            short_name = node.get("attrs", {}).get("shortName")
            if short_name:
                parts.append(short_name)
        elif node_type == "mention":
            attrs = node.get("attrs", {})
            text = attrs.get("text") or attrs.get("displayName")
            if text:
                parts.append(text)
    return "".join(parts)


def _apply_mark(text: str, mark: Dict[str, Any]) -> str:
    mark_type = mark.get("type")
    if mark_type == "strong":
        return f"**{text}**"
    if mark_type == "em":
        return f"*{text}*"
    if mark_type == "code":
        return f"`{text}`"
    if mark_type == "link":
        href = mark.get("attrs", {}).get("href")
        if href:
            return f"[{text}]({href})"
    return text


__all__ = ["to_markdown"]

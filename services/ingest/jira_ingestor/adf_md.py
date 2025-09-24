# Minimal Atlassian Document Format (ADF) -> Markdown converter for common nodes
def to_markdown(adf):
    if not adf or not isinstance(adf, dict):
        return ""
    out = []

    def walk(node):
        t = node.get("type")
        if t == "doc":
            for c in node.get("content", []) or []:
                walk(c)
        elif t == "paragraph":
            out.append("".join(text_runs(node.get("content", []))) + "\n")
        elif t == "heading":
            level = node.get("attrs", {}).get("level", 1)
            hashes = "#" * max(1, min(6, level))
            out.append(hashes + " " + "".join(text_runs(node.get("content", []))) + "\n")
        elif t == "bulletList":
            for li in node.get("content", []) or []:
                # listItem -> paragraph(s)
                for p in li.get("content", []) or []:
                    out.append("- " + "".join(text_runs(p.get("content", []))) + "\n")
        elif t == "orderedList":
            i = 1
            for li in node.get("content", []) or []:
                for p in li.get("content", []) or []:
                    out.append(f"{i}. " + "".join(text_runs(p.get("content", []))) + "\n")
                i += 1
        elif t == "codeBlock":
            lang = node.get("attrs", {}).get("language") or ""
            out.append(f"```{lang}\n")
            for c in node.get("content", []) or []:
                if c.get("type") == "text":
                    out.append(c.get("text",""))
            out.append("\n```\n")
        else:
            for c in node.get("content", []) or []:
                walk(c)

    def text_runs(items):
        segs = []
        for n in items or []:
            if n.get("type") == "text":
                txt = n.get("text","")
                for m in (n.get("marks") or []):
                    mt = m.get("type")
                    if mt == "strong":
                        txt = f"**{txt}**"
                    elif mt == "em":
                        txt = f"*{txt}*"
                    elif mt == "code":
                        txt = f"`{txt}`"
                    elif mt == "link":
                        href = (m.get("attrs") or {}).get("href","")
                        txt = f"[{txt}]({href})"
                segs.append(txt)
        return segs

    walk(adf)
    # collapse excessive blank lines
    md = "".join(out)
    lines = [line.rstrip() for line in md.splitlines()]
    cleaned = []
    last_blank = False
    for line in lines:
        if line.strip() == "":
            if not last_blank:
                cleaned.append("")
            last_blank = True
        else:
            cleaned.append(line)
            last_blank = False
    return "\n".join(cleaned).strip()

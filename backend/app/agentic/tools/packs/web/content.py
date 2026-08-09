"""网页正文提取与截断。"""

import re

from bs4 import BeautifulSoup, NavigableString, Tag

MAX_CONTENT_LEN = 10000
REMOVE_TAGS = ("script", "style", "nav", "footer", "header", "aside", "noscript", "iframe")


class _MarkdownRenderer:
    def render(self, element: Tag | BeautifulSoup) -> str:
        return "".join(self.render_node(child) for child in element.children)

    def inline_text(self, node: Tag) -> str:
        parts = []
        for child in node.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag):
                parts.append(self.render_inline_tag(child))
        return "".join(parts)

    def render_inline_tag(self, node: Tag) -> str:
        tag = node.name
        if tag in ("strong", "b"):
            inner = self.inline_text(node)
            return f"**{inner}**" if inner else ""
        if tag in ("em", "i"):
            inner = self.inline_text(node)
            return f"*{inner}*" if inner else ""
        if tag == "code":
            text = node.get_text()
            return f"`{text}`" if text else ""
        if tag == "a":
            return self.render_link(node)
        if tag == "br":
            return "\n"
        if tag == "img":
            alt = node.get("alt", "").strip()
            return f"[图片: {alt}]" if alt else ""
        return self.inline_text(node)

    def render_link(self, node: Tag) -> str:
        href = node.get("href", "")
        inner = self.inline_text(node).strip()
        if inner and href and not href.startswith(("#", "javascript")):
            return f"[{inner}]({href})"
        return inner

    def render_children(self, node: Tag) -> str:
        return "".join(self.render_node(child) for child in node.children)

    def render_table(self, table: Tag) -> str:
        rows: list[list[str]] = []
        for row_element in table.find_all("tr"):
            cells = [
                self.inline_text(cell).strip().replace("|", "\\|")
                for cell in row_element.find_all(["th", "td"])
            ]
            rows.append(cells)
        if not rows:
            return ""

        max_columns = max(len(row) for row in rows)
        for row in rows:
            row.extend([""] * (max_columns - len(row)))
        lines = [
            "| " + " | ".join(rows[0]) + " |",
            "| " + " | ".join(["---"] * max_columns) + " |",
        ]
        lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
        return "\n\n" + "\n".join(lines) + "\n\n"

    def render_list(self, node: Tag) -> str:
        items = []
        for index, item in enumerate(node.find_all("li", recursive=False), 1):
            inner = self.render_children(item).strip()
            if inner:
                prefix = "-" if node.name == "ul" else f"{index}."
                items.append(f"{prefix} {inner}")
        return "\n\n" + "\n".join(items) + "\n\n" if items else ""

    def render_blockquote(self, node: Tag) -> str:
        inner = self.render_children(node).strip()
        if not inner:
            return ""
        quoted = "\n".join(f"> {line}" for line in inner.split("\n"))
        return f"\n\n{quoted}\n\n"

    def render_node(self, node: Tag | NavigableString) -> str:
        if isinstance(node, NavigableString):
            text = str(node)
            return text if text.strip() else ""
        if not isinstance(node, Tag) or node.name in REMOVE_TAGS:
            return ""

        tag = node.name
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            inner = self.inline_text(node).strip()
            return f"\n\n{'#' * int(tag[1])} {inner}\n\n" if inner else ""
        if tag == "p":
            inner = self.inline_text(node).strip()
            return f"\n\n{inner}\n\n" if inner else ""
        if tag == "br":
            return "\n"
        if tag in ("strong", "b"):
            inner = self.inline_text(node).strip()
            return f"**{inner}**" if inner else ""
        if tag in ("em", "i"):
            inner = self.inline_text(node).strip()
            return f"*{inner}*" if inner else ""
        if tag == "code" and not (node.parent and node.parent.name == "pre"):
            text = node.get_text()
            return f"`{text}`" if text else ""
        if tag == "pre":
            code_element = node.find("code")
            text = code_element.get_text() if code_element else node.get_text()
            return f"\n\n```\n{text}\n```\n\n"
        if tag == "a":
            return self.render_link(node)
        if tag == "img":
            alt = node.get("alt", "").strip()
            return f"[图片: {alt}]" if alt else ""
        if tag == "blockquote":
            return self.render_blockquote(node)
        if tag == "hr":
            return "\n\n---\n\n"
        if tag in ("ul", "ol"):
            return self.render_list(node)
        if tag == "table":
            return self.render_table(node)
        return self.render_children(node)


def html_to_markdown(element: Tag | BeautifulSoup) -> str:
    """Convert a BeautifulSoup tree to lightweight Markdown."""
    return _MarkdownRenderer().render(element)


def extract_meta(soup: BeautifulSoup) -> dict[str, str]:
    """Extract useful Open Graph and article metadata."""
    meta: dict[str, str] = {}

    def meta_content(property_name: str) -> str:
        element = soup.find("meta", attrs={"property": property_name}) or soup.find(
            "meta",
            attrs={"name": property_name},
        )
        if element and element.get("content"):
            return str(element["content"]).strip()
        return ""

    for key in ("og:title", "og:description", "og:image"):
        if value := meta_content(key):
            meta[key] = value
    for key in ("article:published_time", "article:author", "article:section"):
        if value := meta_content(key):
            meta[key] = value
    if description := meta_content("description"):
        meta["description"] = description
    if keywords := meta_content("keywords"):
        meta["keywords"] = keywords

    canonical = soup.find("link", attrs={"rel": "canonical"})
    if canonical and canonical.get("href"):
        meta["canonical_url"] = canonical["href"].strip()
    return meta


def extract_text(html: str) -> tuple[dict[str, str], tuple[str, str]]:
    """Extract metadata, title, and Markdown content from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    meta = extract_meta(soup)
    for tag_name in REMOVE_TAGS:
        for tag in soup.find_all(tag_name):
            tag.decompose()

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    if not title:
        title = meta.get("og:title", "")
    main = soup.find("article") or soup.find("main") or soup.find("body") or soup
    text = re.sub(r"\n{3,}", "\n\n", html_to_markdown(main)).strip()
    return meta, (title, text)


def smart_truncate(text: str, max_len: int = MAX_CONTENT_LEN) -> tuple[str, bool]:
    """Truncate at a nearby paragraph or sentence boundary."""
    if len(text) <= max_len:
        return text, False

    search_start = max(0, max_len - 500)
    chunk = text[search_start:max_len]
    last_paragraph = chunk.rfind("\n\n")
    if last_paragraph > 0:
        return text[: search_start + last_paragraph].rstrip(), True

    last_sentence = max(chunk.rfind(separator) for separator in ("！", "。", "？", "!", ".", "?", "\n"))
    if last_sentence > 0:
        return text[: search_start + last_sentence + 1].rstrip(), True
    return text[:max_len], True

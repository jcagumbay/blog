"""WordPress WXR -> Jekyll markdown converter.

Reads codetravelrepeat.WordPress.2026-04-28.xml in this directory and writes:
  _posts/YYYY-MM-DD-slug.md   (published posts)
  _pages/slug.md              (published pages)

Image URLs pointing at the original WordPress site are rewritten to local
/assets/wp-content/uploads/... paths so they can be served from the repo
after running download_assets.py.
"""
from __future__ import annotations

import os
import re
import sys
import html
import datetime as dt
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from markdownify import markdownify as md

ROOT = Path(__file__).resolve().parent
XML_FILE = ROOT / "codetravelrepeat.WordPress.2026-04-28.xml"
POSTS_DIR = ROOT / "_posts"
PAGES_DIR = ROOT / "_pages"
CAT_DIR = ROOT / "_category"
TAG_DIR = ROOT / "_tag"

NS = {
    "wp": "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

# Match the WordPress site's hosted image URLs (http or https, with/without www).
WP_HOST_RE = re.compile(
    r"https?://(?:www\.)?jboy\.cagumbay\.com(/wp-content/uploads/[^\s\"'<>)]+)",
    re.IGNORECASE,
)

CAPTION_RE = re.compile(
    r"\[caption[^\]]*\](.*?)\[/caption\]",
    re.IGNORECASE | re.DOTALL,
)

GALLERY_RE = re.compile(r"\[gallery[^\]]*\]", re.IGNORECASE)

# First <img src="..."> in content (after URL rewrite this points at /assets/...)
IMG_SRC_RE = re.compile(r'<img[^>]*\bsrc="([^"]+)"', re.IGNORECASE)

# Inside [caption]...[/caption] separate img markup from trailing caption text
CAPTION_IMG_RE = re.compile(
    r'(?P<img>(?:<a[^>]*>\s*)?<img[^>]*?/?>(?:\s*</a>)?)\s*(?P<txt>.*)',
    re.IGNORECASE | re.DOTALL,
)


def text(elem, path, ns=NS, default=""):
    node = elem.find(path, ns)
    if node is None or node.text is None:
        return default
    return node.text


def yaml_escape(value: str) -> str:
    """Quote a string safely for YAML scalar use."""
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def slugify_fallback(s: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "untitled"


def rewrite_image_urls(content: str) -> str:
    return WP_HOST_RE.sub(r"/assets\1", content)


def strip_shortcodes(content: str, figures: list) -> str:
    """Replace [caption] blocks with placeholder tokens. The matching figure
    HTML is appended to the supplied list at the corresponding index."""

    def repl(m):
        inner = m.group(1).strip()
        sub = CAPTION_IMG_RE.match(inner)
        if not sub:
            figures.append(inner)
        else:
            img_html = sub.group("img").strip()
            caption_text = sub.group("txt").strip()
            # alt attr can hold long sentences; we strip that down so markdown
            # alt text stays short. The caption (figcaption) carries the prose.
            img_html = re.sub(r'\salt="[^"]*"', '', img_html, count=1)
            if caption_text:
                fig = (
                    '<figure class="wp-caption">\n'
                    f'{img_html}\n'
                    f'<figcaption class="wp-caption-text">{caption_text}</figcaption>\n'
                    '</figure>'
                )
            else:
                fig = img_html
            figures.append(fig)
        return f"\n\nMDXFIG{len(figures) - 1}MDXFIG\n\n"

    content = CAPTION_RE.sub(repl, content)
    content = GALLERY_RE.sub("", content)
    return content


def parse_post_date(raw: str) -> dt.datetime | None:
    if not raw or raw.startswith("0000"):
        return None
    try:
        return dt.datetime.strptime(raw, "%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def collect_terms(item):
    cats, tags = [], []
    for c in item.findall("category"):
        domain = c.get("domain", "")
        name = (c.text or "").strip()
        if not name:
            continue
        if domain == "category":
            cats.append(name)
        elif domain == "post_tag":
            tags.append(name)
    # de-dup, preserve order
    cats = list(dict.fromkeys(cats))
    tags = list(dict.fromkeys(tags))
    return cats, tags


def build_front_matter(*, layout, title, date, slug, categories, tags,
                       excerpt, original_url, post_id, author, image=None):
    lines = ["---"]
    lines.append(f"layout: {layout}")
    lines.append(f"title: {yaml_escape(title)}")
    if date is not None:
        lines.append(f"date: {date.strftime('%Y-%m-%d %H:%M:%S')} +0000")
    lines.append(f"slug: {yaml_escape(slug)}")
    if image:
        lines.append(f"image: {yaml_escape(image)}")
    if author:
        lines.append(f"author: {yaml_escape(author)}")
    if categories:
        lines.append("categories:")
        for c in categories:
            lines.append(f"  - {yaml_escape(c)}")
    if tags:
        lines.append("tags:")
        for t in tags:
            lines.append(f"  - {yaml_escape(t)}")
    if excerpt:
        lines.append(f"excerpt: {yaml_escape(excerpt)}")
    if original_url:
        lines.append(f"original_url: {yaml_escape(original_url)}")
    if post_id:
        lines.append(f"wordpress_id: {post_id}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


BLOCK_TAGS_RE = re.compile(
    r'^\s*<(?:figure|p|div|ul|ol|li|h[1-6]|blockquote|pre|table|hr|iframe|MDXFIG)',
    re.IGNORECASE,
)


def wpautop(content: str) -> str:
    """Wrap double-newline separated text blocks in <p> like WordPress does."""
    blocks = re.split(r'\n\s*\n+', content.strip())
    out = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        if BLOCK_TAGS_RE.match(b) or b.startswith("MDXFIG"):
            out.append(b)
        else:
            out.append(f"<p>{b}</p>")
    return "\n\n".join(out)


def html_to_markdown(html_content: str) -> str:
    # markdownify options: keep image alt/title, ATX headings, no auto-linking
    # of bare URLs (we keep formatting close to WP output).
    return md(
        html_content,
        heading_style="ATX",
        bullets="-",
        strip=["script", "style"],
    )


def post_filename(date: dt.datetime, slug: str) -> str:
    return f"{date.strftime('%Y-%m-%d')}-{slug}.md"


def build_attachment_map(items):
    """post_id -> rewritten /assets/... URL"""
    m = {}
    for item in items:
        if text(item, "wp:post_type") != "attachment":
            continue
        pid = text(item, "wp:post_id").strip()
        au = item.find("wp:attachment_url", NS)
        if pid and au is not None and au.text:
            m[pid] = rewrite_image_urls(au.text.strip())
    return m


def featured_image(item, att_map):
    for pm in item.findall("wp:postmeta", NS):
        k = pm.find("wp:meta_key", NS)
        v = pm.find("wp:meta_value", NS)
        if k is not None and k.text == "_thumbnail_id" and v is not None and v.text:
            tid = v.text.strip()
            return att_map.get(tid)
    return None


def main():
    if not XML_FILE.exists():
        sys.exit(f"missing {XML_FILE}")

    POSTS_DIR.mkdir(exist_ok=True)
    PAGES_DIR.mkdir(exist_ok=True)
    CAT_DIR.mkdir(exist_ok=True)
    TAG_DIR.mkdir(exist_ok=True)

    tree = ET.parse(XML_FILE)
    channel = tree.getroot().find("channel")
    items = channel.findall("item")
    att_map = build_attachment_map(items)

    written_posts = 0
    written_pages = 0
    skipped = 0

    for item in items:
        post_type = text(item, "wp:post_type")
        status = text(item, "wp:status")
        if post_type not in ("post", "page"):
            continue
        if status != "publish":
            skipped += 1
            continue

        title = (item.findtext("title") or "").strip()
        raw_content = text(item, "content:encoded")
        excerpt = text(item, "excerpt:encoded").strip()
        slug = text(item, "wp:post_name").strip() or slugify_fallback(title)
        post_id = text(item, "wp:post_id").strip()
        author = (item.findtext("{http://purl.org/dc/elements/1.1/}creator") or "").strip()
        original_url = (item.findtext("link") or "").strip()
        date = parse_post_date(text(item, "wp:post_date_gmt")) \
               or parse_post_date(text(item, "wp:post_date"))
        if date is None:
            # last resort: pubDate
            try:
                date = dt.datetime.strptime(
                    item.findtext("pubDate"), "%a, %d %b %Y %H:%M:%S %z"
                ).replace(tzinfo=None)
            except Exception:
                date = dt.datetime.utcnow()

        cats, tags = collect_terms(item)

        # decode HTML entities WordPress encodes inside CDATA escapes
        content = raw_content or ""
        figures: list[str] = []
        content = strip_shortcodes(content, figures)
        content = rewrite_image_urls(content)
        figures = [rewrite_image_urls(f) for f in figures]
        # Featured image: prefer _thumbnail_id, fallback to first inline <img>
        first_img = featured_image(item, att_map)
        if not first_img:
            m = IMG_SRC_RE.search(content)
            if not m and figures:
                m = IMG_SRC_RE.search("\n".join(figures))
            if m:
                first_img = m.group(1)
        # Convert excerpt similarly
        excerpt_text = ""
        if excerpt:
            excerpt_clean = strip_shortcodes(rewrite_image_urls(excerpt))
            excerpt_text = html_to_markdown(excerpt_clean).strip()
            # collapse whitespace
            excerpt_text = re.sub(r"\s+", " ", excerpt_text)

        content = wpautop(content)
        body_md = html_to_markdown(content).strip()
        # Restore figure blocks that we tokenised before markdownify so they
        # survive as raw HTML (kramdown passes block-level HTML through).
        for idx, fig in enumerate(figures):
            body_md = body_md.replace(f"MDXFIG{idx}MDXFIG", fig)
        body_md += "\n"

        if post_type == "post":
            front = build_front_matter(
                layout="post",
                title=title or slug,
                date=date,
                slug=slug,
                categories=cats,
                tags=tags,
                excerpt=excerpt_text,
                original_url=original_url,
                post_id=post_id,
                author=author,
                image=first_img,
            )
            fname = post_filename(date, slug)
            (POSTS_DIR / fname).write_text(front + body_md, encoding="utf-8")
            written_posts += 1
        else:  # page
            front = build_front_matter(
                layout="page",
                title=title or slug,
                date=date,
                slug=slug,
                categories=[],
                tags=[],
                excerpt=excerpt_text,
                original_url=original_url,
                post_id=post_id,
                author=author,
            )
            # add permalink for pages so URL matches the slug
            front = front.replace("---\n\n", "", 1)  # not used; keep front intact
            page_md = (
                f"---\nlayout: page\ntitle: {yaml_escape(title or slug)}\n"
                f"permalink: /{slug}/\n"
                + (f"original_url: {yaml_escape(original_url)}\n" if original_url else "")
                + "---\n\n"
                + body_md
            )
            (PAGES_DIR / f"{slug}.md").write_text(page_md, encoding="utf-8")
            written_pages += 1

    print(f"posts written: {written_posts}")
    print(f"pages written: {written_pages}")
    print(f"non-published items skipped: {skipped}")

    # Build category/tag archive pages
    cat_terms, tag_terms = {}, {}
    for item in items:
        if text(item, "wp:post_type") != "post":
            continue
        if text(item, "wp:status") != "publish":
            continue
        cs, ts = collect_terms(item)
        for c in cs:
            cat_terms[c] = slugify_fallback(c)
        for t in ts:
            tag_terms[t] = slugify_fallback(t)

    def write_archive(directory, kind, name, slug):
        path = directory / f"{slug}.md"
        body = (
            "---\n"
            f"layout: archive\n"
            f"kind: {kind}\n"
            f"term: {yaml_escape(name)}\n"
            f"slug: {yaml_escape(slug)}\n"
            f"title: {yaml_escape(name)}\n"
            f"permalink: /{kind}/{slug}/\n"
            "---\n"
        )
        path.write_text(body, encoding="utf-8")

    for name, slug in cat_terms.items():
        write_archive(CAT_DIR, "category", name, slug)
    for name, slug in tag_terms.items():
        write_archive(TAG_DIR, "tag", name, slug)

    print(f"category archives: {len(cat_terms)}")
    print(f"tag archives: {len(tag_terms)}")


if __name__ == "__main__":
    main()

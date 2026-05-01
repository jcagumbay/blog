#!/usr/bin/env python3
"""Scaffold a new Jekyll post.

Usage:
    new_post.py "My Post Title" [--slug custom-slug] [--cat Travel] \
                [--tag tag1 --tag tag2] [--date 2026-05-01]

Creates:
    _posts/YYYY-MM-DD-<slug>.md       (front matter + placeholder body)
    assets/wp-content/uploads/YYYY/MM/  (empty dir — drop images here)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "_posts"
UPLOADS_ROOT = ROOT / "assets" / "wp-content" / "uploads"


def slugify(s: str) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "untitled"


def yaml_str(v: str) -> str:
    return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("title", help="Post title")
    p.add_argument("--slug", help="Override auto-slug")
    p.add_argument("--date", help="YYYY-MM-DD (default: today)")
    p.add_argument("--cat", action="append", default=[], help="Category (repeatable)")
    p.add_argument("--tag", action="append", default=[], help="Tag (repeatable)")
    p.add_argument("--no-edit", action="store_true", help="Skip $EDITOR launch")
    args = p.parse_args()

    if args.date:
        try:
            date = dt.datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print("--date must be YYYY-MM-DD", file=sys.stderr)
            return 2
    else:
        date = dt.datetime.now()

    slug = args.slug or slugify(args.title)
    fname = f"{date:%Y-%m-%d}-{slug}.md"
    post_path = POSTS_DIR / fname
    if post_path.exists():
        print(f"refuse to overwrite: {post_path}", file=sys.stderr)
        return 1

    upload_dir = UPLOADS_ROOT / f"{date:%Y}" / f"{date:%m}"
    upload_dir.mkdir(parents=True, exist_ok=True)

    cats = args.cat or ["Travel"]

    front_lines = [
        "---",
        "layout: post",
        f"title: {yaml_str(args.title)}",
        f"date: {date:%Y-%m-%d %H:%M:%S} +0000",
        f"slug: {yaml_str(slug)}",
        f'image: "/assets/wp-content/uploads/{date:%Y}/{date:%m}/REPLACE_ME.jpg"',
        'author: "jb.cagumbay@gmail.com"',
        "categories:",
    ]
    front_lines += [f"  - {yaml_str(c)}" for c in cats]
    if args.tag:
        front_lines.append("tags:")
        front_lines += [f"  - {yaml_str(t)}" for t in args.tag]
    front_lines.append("---\n")

    body = (
        "Intro paragraph.\n\n"
        "Second paragraph.\n\n"
        "<figure class=\"wp-caption\">\n"
        f'<img src="/assets/wp-content/uploads/{date:%Y}/{date:%m}/REPLACE_ME.jpg" />\n'
        "<figcaption class=\"wp-caption-text\">Caption text</figcaption>\n"
        "</figure>\n"
    )

    post_path.write_text("\n".join(front_lines) + "\n" + body, encoding="utf-8")
    print(f"created {post_path.relative_to(ROOT)}")
    print(f"upload images to {upload_dir.relative_to(ROOT)}/")

    if not args.no_edit:
        editor = os.environ.get("EDITOR")
        if editor:
            os.execvp(editor, [editor, str(post_path)])
    return 0


if __name__ == "__main__":
    sys.exit(main())

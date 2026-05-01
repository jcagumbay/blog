"""Convert WP Google Maps CSV export to Jekyll _data/locations.json.

Pulls redirect_link out of the PHP-serialized location_settings column,
rewrites the WordPress URL to its Jekyll permalink (/YYYY/MM/DD/slug/),
and writes a clean JSON list ready for Liquid consumption.
"""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_FILE = ROOT / "map_locations.csv"
POSTS_DIR = ROOT / "_posts"
DATA_DIR = ROOT / "_data"
OUT = DATA_DIR / "locations.json"

REDIRECT_RE = re.compile(
    r's:13:"redirect_link";s:\d+:"([^"]+)"',
    re.IGNORECASE,
)
WP_HOST_RE = re.compile(
    r"https?://(?:www\.)?jboy\.cagumbay\.com/([^/?#]+)/?",
    re.IGNORECASE,
)
POST_FILE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(.+)\.md$")


def build_slug_index() -> dict[str, str]:
    """slug -> Jekyll permalink (using configured permalink format)."""
    idx = {}
    for p in POSTS_DIR.glob("*.md"):
        m = POST_FILE_RE.match(p.name)
        if not m:
            continue
        y, mo, d, slug = m.groups()
        idx[slug] = f"/{y}/{mo}/{d}/{slug}/"
    return idx


def extract_redirect(settings: str) -> str | None:
    if not settings:
        return None
    m = REDIRECT_RE.search(settings)
    return m.group(1) if m else None


def to_local_url(wp_url: str, slug_index: dict) -> str | None:
    if not wp_url:
        return None
    m = WP_HOST_RE.match(wp_url.strip())
    if not m:
        return wp_url  # external URL — leave as is
    slug = m.group(1)
    return slug_index.get(slug)


def main():
    DATA_DIR.mkdir(exist_ok=True)
    slug_index = build_slug_index()

    out = []
    skipped = 0
    with open(CSV_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                lat = float(row["location_latitude"])
                lng = float(row["location_longitude"])
            except (TypeError, ValueError):
                skipped += 1
                continue

            wp_url = extract_redirect(row.get("location_settings") or "")
            url = to_local_url(wp_url, slug_index) if wp_url else None

            out.append({
                "id": int(row["location_id"]),
                "title": (row.get("location_title") or "").strip(),
                "address": (row.get("location_address") or "").strip(),
                "lat": lat,
                "lng": lng,
                "city": (row.get("location_city") or "").strip(),
                "state": (row.get("location_state") or "").strip(),
                "country": (row.get("location_country") or "").strip(),
                "url": url,
                "external_url": wp_url if url is None and wp_url else None,
            })

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    matched = sum(1 for r in out if r["url"])
    print(f"locations: {len(out)}")
    print(f"matched to local posts: {matched}")
    print(f"skipped (bad coords): {skipped}")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

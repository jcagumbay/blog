"""Download every WordPress attachment in the WXR export into ./assets/.

Local layout mirrors the original WP path:
    https://jboy.cagumbay.com/wp-content/uploads/2015/06/foo.jpg
        -> assets/wp-content/uploads/2015/06/foo.jpg

Skips files already present so the script is resumable.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.parse
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent
XML_FILE = ROOT / "codetravelrepeat.WordPress.2026-04-28.xml"
ASSETS = ROOT / "assets"
NS = {"wp": "http://wordpress.org/export/1.2/"}

CONCURRENCY = 16
TIMEOUT = 30
RETRIES = 3
USER_AGENT = "Mozilla/5.0 (Jekyll migration script)"


def collect_urls():
    tree = ET.parse(XML_FILE)
    channel = tree.getroot().find("channel")
    urls = []
    for item in channel.findall("item"):
        ptype = item.findtext("wp:post_type", namespaces=NS)
        if ptype != "attachment":
            continue
        url = item.findtext("wp:attachment_url", namespaces=NS)
        if url:
            urls.append(url.strip())
    # de-dup
    return list(dict.fromkeys(urls))


def local_path_for(url: str) -> Path | None:
    parsed = urllib.parse.urlparse(url)
    path = urllib.parse.unquote(parsed.path)
    if "/wp-content/" not in path:
        return None
    rel = path.lstrip("/")
    return ASSETS / rel


def download_one(session: requests.Session, url: str) -> tuple[str, str]:
    dest = local_path_for(url)
    if dest is None:
        return url, "skip-non-wp-content"
    if dest.exists() and dest.stat().st_size > 0:
        return url, "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_err = None
    for attempt in range(1, RETRIES + 1):
        try:
            with session.get(url, timeout=TIMEOUT, stream=True,
                             headers={"User-Agent": USER_AGENT}) as r:
                if r.status_code == 404:
                    return url, "404"
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(chunk_size=64 * 1024):
                        if chunk:
                            f.write(chunk)
                tmp.rename(dest)
                return url, "ok"
        except Exception as e:
            last_err = e
            time.sleep(min(2 ** attempt, 8))
    return url, f"fail:{last_err}"


def main():
    urls = collect_urls()
    print(f"attachments: {len(urls)}")
    ASSETS.mkdir(exist_ok=True)
    results = {"ok": 0, "exists": 0, "404": 0, "fail": 0, "skip-non-wp-content": 0}
    failed_urls = []

    with requests.Session() as session, \
         ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        futures = [pool.submit(download_one, session, u) for u in urls]
        for i, fut in enumerate(as_completed(futures), 1):
            url, status = fut.result()
            key = "fail" if status.startswith("fail") else status
            results[key] = results.get(key, 0) + 1
            if key == "fail":
                failed_urls.append((url, status))
            if i % 100 == 0 or i == len(urls):
                print(f"  {i}/{len(urls)} {results}")

    print("done:", results)
    if failed_urls:
        log = ROOT / "download_failures.log"
        with open(log, "w") as f:
            for u, s in failed_urls:
                f.write(f"{u}\t{s}\n")
        print(f"failures logged: {log}")


if __name__ == "__main__":
    main()

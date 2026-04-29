"""Download every WordPress image URL *referenced* in post/page content
that isn't already on disk. WP generates resized variants
(e.g. -1024x683) that don't appear in the WXR attachment list."""
from __future__ import annotations
import re, time, urllib.parse, xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
XML_FILE = ROOT / "codetravelrepeat.WordPress.2026-04-28.xml"
ASSETS = ROOT / "assets"
NS = {"wp": "http://wordpress.org/export/1.2/",
      "content": "http://purl.org/rss/1.0/modules/content/"}
URL_RE = re.compile(
    r"https?://(?:www\.)?jboy\.cagumbay\.com/wp-content/uploads/[^\s\"'<>)]+",
    re.IGNORECASE,
)
CONCURRENCY = 16
TIMEOUT = 30
RETRIES = 3
UA = "Mozilla/5.0 (Jekyll migration script)"


def collect():
    tree = ET.parse(XML_FILE)
    ch = tree.getroot().find("channel")
    urls = set()
    for item in ch.findall("item"):
        pt = item.findtext("wp:post_type", namespaces=NS)
        if pt not in ("post", "page"):
            continue
        c = item.find("content:encoded", NS)
        if c is None or not c.text:
            continue
        for m in URL_RE.finditer(c.text):
            urls.add(m.group(0))
    return urls


def local(url):
    p = urllib.parse.urlparse(url)
    return ASSETS / urllib.parse.unquote(p.path).lstrip("/")


def fetch(s, url):
    dest = local(url)
    if dest.exists() and dest.stat().st_size > 0:
        return url, "exists"
    dest.parent.mkdir(parents=True, exist_ok=True)
    last = None
    for attempt in range(1, RETRIES + 1):
        try:
            with s.get(url, timeout=TIMEOUT, stream=True,
                       headers={"User-Agent": UA}) as r:
                if r.status_code == 404:
                    return url, "404"
                r.raise_for_status()
                tmp = dest.with_suffix(dest.suffix + ".part")
                with open(tmp, "wb") as f:
                    for chunk in r.iter_content(64 * 1024):
                        if chunk:
                            f.write(chunk)
                tmp.rename(dest)
                return url, "ok"
        except Exception as e:
            last = e
            time.sleep(min(2 ** attempt, 8))
    return url, f"fail:{last}"


def main():
    urls = collect()
    print(f"referenced URLs: {len(urls)}")
    ASSETS.mkdir(exist_ok=True)
    res = {"ok": 0, "exists": 0, "404": 0, "fail": 0}
    fails = []
    with requests.Session() as s, ThreadPoolExecutor(CONCURRENCY) as p:
        futs = [p.submit(fetch, s, u) for u in urls]
        for i, f in enumerate(as_completed(futs), 1):
            u, st = f.result()
            k = "fail" if st.startswith("fail") else st
            res[k] = res.get(k, 0) + 1
            if k == "fail":
                fails.append((u, st))
            if i % 200 == 0 or i == len(urls):
                print(f"  {i}/{len(urls)} {res}")
    print("done:", res)
    if fails:
        log = ROOT / "download_referenced_failures.log"
        with open(log, "w") as f:
            for u, s in fails:
                f.write(f"{u}\t{s}\n")
        print("failures:", log)


if __name__ == "__main__":
    main()

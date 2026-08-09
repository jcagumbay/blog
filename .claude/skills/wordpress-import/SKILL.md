---
name: wordpress-import
description: Import posts from a WordPress WXR export into this Jekyll blog — convert the XML to markdown, download the attachments, and sync them to R2. Use when the user has a new WordPress export file, mentions a WXR or codetravelrepeat.WordPress.*.xml, or wants to re-run the migration.
---

# Importing a WordPress export

The blog was migrated off WordPress, but posts are still authored there
occasionally and exported. The scripts live in `tools/wordpress-converter/` and
resolve paths off `__file__`, so they run from anywhere.

They are **additive** — they write the items in the export and leave everything
else alone. Re-running on an old export is safe and produces byte-identical
output.

## Run it

Drop the WXR into `tools/wordpress-converter/exports/`, then from the repo root:

```sh
E=tools/wordpress-converter/exports/<file>.xml

.venv/bin/python tools/wordpress-converter/convert.py             "$E"
.venv/bin/python tools/wordpress-converter/download_assets.py     "$E"
.venv/bin/python tools/wordpress-converter/download_referenced.py "$E"
```

With no path argument they pick the newest-named XML in `exports/`.

- `convert.py` → `_posts/`, `_pages/`, and `_category/`/`_tag/` archive pages
  for every term it sees
- `download_assets.py` → attachments listed in the export
- `download_referenced.py` → WordPress-generated size variants (`-1024x683`
  etc.) that appear in post bodies but not the attachment list

Then sync the new month to R2 (see the `r2-sync` skill) and add map markers for
the new posts (see `new-post`, step 5). Neither is automated.

## Scheduled posts

`convert.py` writes only `wp:status == "publish"`. A post scheduled in
WordPress exports as `future` and is skipped — the run reports it as
`non-published items skipped`. Its attachments still download.

`--include-future` emits those too. The markdown lands with its scheduled date,
and Jekyll won't render it until a build runs on or after that date — there is
no cron, so that means a manual `gh workflow run jekyll.yml`. Tell the user
this rather than letting them assume it self-publishes.

## Check the export parses first

```sh
python3 -c "import xml.etree.ElementTree as ET; ET.parse('$E'); print('ok')"
```

Editors that strip trailing whitespace or auto-format on save will corrupt a
WXR file — this has happened. If the file is tracked and parsing fails, diff it
against `HEAD` with `--ignore-all-space` to see whether the only real change is
damage, and restore with `git checkout HEAD -- <file>`.

## What to check after a run

- Post count matches what the export contained
- Every `src` in the new posts exists on disk (see `new-post`, step 3)
- New tags got `_tag/<slug>.md` files — `git status` shows them
- `original_url` on a converted scheduled post is the `?p=<id>` form rather
  than a pretty permalink, because WordPress hasn't published it yet.
  Harmless; re-converting after publication fixes it.

## Do not run parse_locations.py

It is in the same directory and looks like part of this flow. It is not.
It rebuilds `_data/locations.json` wholesale from a 164-row CSV, deleting every
marker added since the migration and reintroducing a fixed bug. Add markers by
hand instead.

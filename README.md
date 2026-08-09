# code. travel. repeat.

Jekyll source for [jcagumbay.github.io/blog](https://jcagumbay.github.io/blog/), migrated from a WordPress export.

- 214 posts + 6 pages converted from WXR
- Custom theme: square-tile home, post detail with sidebar, category/tag archives, Google Maps "Where I've Been"
- Images served from Cloudflare R2 (rewritten at CI build); local dev still uses on-disk `assets/`

## Stack

- Jekyll 3.x via `github-pages` gem
- Custom layouts (no minima theme)
- Plugins (GH Pages whitelisted): `jekyll-feed`, `jekyll-seo-tag`, `jekyll-sitemap`, `jekyll-paginate`
- Image hosting: Cloudflare R2 bucket `jboy-cagumbay-com`
- Map: Google Maps JavaScript API

## Repo layout

| Path | Purpose |
|------|---------|
| `_posts/` | One markdown file per blog post |
| `_pages/` | Static pages (About, Travel Tips, etc.) |
| `_category/`, `_tag/` | Pre-generated archive pages (avoids `jekyll-archives` plugin) |
| `_layouts/` | Templates: default, home, post, page, archive, map |
| `_includes/` | header, footer, sidebar |
| `_data/` | Site data — `locations.json` (map markers), `api_keys.yml` (gitignored) |
| `assets/css/main.css` | Theme styles |
| `assets/wp-content/uploads/` | Images (gitignored, mirrored to R2) |
| `tools/new-post/` | `new_post.py` — scaffold a new post. The only tool in routine use |
| `tools/wordpress-converter/` | One-shot migration scripts + their inputs (see below) |
| `.github/workflows/jekyll.yml` | Build + deploy to GitHub Pages, rewrite asset URLs to R2 |

### `tools/wordpress-converter/`

Retired after the migration — kept for re-importing a later WordPress export.

| Path | Purpose |
|------|---------|
| `convert.py` | WXR → posts/pages/archives generator |
| `download_assets.py` | Pull WP attachments listed in WXR |
| `download_referenced.py` | Pull WP-generated variants referenced in post content |
| `parse_locations.py` | WP Google Maps CSV → `_data/locations.json` |
| `exports/` | WXR XML exports |
| `map_locations.csv` | WP Google Maps plugin dump, input to `parse_locations.py` |

> **`parse_locations.py` is effectively retired.** `_data/locations.json` is now
> the source of truth and is edited by hand — see "Adding a map marker". The
> script rebuilds that file wholesale from the 164-row CSV, so running it drops
> any marker added since the migration. Only run it after re-exporting the CSV
> from WordPress.

## Local development

Requires Docker.

```sh
docker volume create jekyll-bundle
docker run -d --rm --name jekyll-preview \
  -v "$PWD:/srv/jekyll" \
  -v jekyll-bundle:/usr/local/bundle \
  -p 4000:4000 \
  jekyll/jekyll:latest \
  jekyll serve --host 0.0.0.0 --watch --incremental
```

- http://localhost:4000/
- Auto-rebuild on file change
- Restart container after `_config.yml` change: `docker restart jekyll-preview`
- Clean rebuild: `docker exec jekyll-preview rm -rf /srv/jekyll/_site /srv/jekyll/.jekyll-cache /srv/jekyll/.jekyll-metadata && docker restart jekyll-preview`

To preview the map locally, copy the example key file:

```sh
cp _data/api_keys.example.yml _data/api_keys.yml
# edit _data/api_keys.yml — set your Google Maps browser key
```

## Adding a new post

```sh
./tools/new-post/new_post.py "Title of the Post" --cat Travel --tag city --tag country
```

This creates:

- `_posts/YYYY-MM-DD-title-of-the-post.md` with front matter + placeholder figure
- `assets/wp-content/uploads/YYYY/MM/` directory (drop image files here)

Edit the post, drop hero + body images into the `YYYY/MM/` folder. Then:

```sh
# 1. upload only the new month's images to R2 (fast)
rclone sync assets/wp-content/uploads/YYYY/MM/ \
  r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" \
  --progress

# 2. if you used a brand-new tag or category, regenerate archive pages
.venv/bin/python tools/wordpress-converter/convert.py   # only if migrating; for ad-hoc tags see below

# 3. commit + push — CI rewrites /assets/... -> R2 URL and deploys
git add _posts/YYYY-MM-DD-*.md _category/ _tag/
git commit -m "post: <title>"
git push
```

> **New tag/category note**: archive pages are pre-generated. After introducing a tag that doesn't exist yet, create `_tag/<slug>.md`:
> ```yaml
> ---
> layout: archive
> kind: tag
> term: "<tag display name>"
> slug: "<tag-slug>"
> title: "<tag display name>"
> permalink: /tag/<tag-slug>/
> ---
> ```
> Same shape for `_category/<slug>.md` (with `kind: category`).

## Adding a map marker

Edit `_data/locations.json` directly:

```json
{
  "id": 165,
  "title": "Place",
  "lat": 12.34,
  "lng": 56.78,
  "city": "City",
  "country": "Country",
  "url": "/YYYY/MM/DD/post-slug/"
}
```

Or re-export `map_locations.csv` from WP and run
`tools/wordpress-converter/parse_locations.py` — but read the warning above
first, it overwrites hand-added markers.

## Deployment

Pushing to `main` triggers `.github/workflows/jekyll.yml`:

1. Setup Ruby + bundler
2. Configure GitHub Pages
3. Write `_data/api_keys.yml` from secret `GOOGLE_MAPS_API_KEY`
4. Rewrite `/assets/wp-content/` → `${{ vars.CDN_URL }}/wp-content/` in source files
5. `bundle exec jekyll build`
6. Deploy via `actions/deploy-pages`

### Required GitHub config

| Type | Name | Value |
|------|------|-------|
| Variable | `CDN_URL` | `https://4e8d99e3.cagumbay.com` (R2 custom domain) |
| Secret   | `GOOGLE_MAPS_API_KEY` | Browser-restricted Google Maps API key |

Set with:

```sh
gh variable set CDN_URL --repo jcagumbay/blog --body "https://4e8d99e3.cagumbay.com"
gh secret set GOOGLE_MAPS_API_KEY --repo jcagumbay/blog
```

### Pages settings

Settings → Pages → Source: **GitHub Actions** (already enabled via API).

## R2 bucket

Bucket: `jboy-cagumbay-com`. Public via R2.dev subdomain.

```sh
# one-time configure
rclone config create r2 s3 \
  provider=Cloudflare \
  access_key_id=<KEY> \
  secret_access_key=<SECRET> \
  endpoint=https://<account_id>.r2.cloudflarestorage.com \
  no_check_bucket=true

# bulk upload (resumable)
rclone sync assets/wp-content/uploads/ r2:jboy-cagumbay-com/wp-content/uploads/ \
  --transfers=16 --checkers=16 --checksum --progress \
  --header-upload "Cache-Control: public, max-age=31536000, immutable"
```

## Re-running the migration from scratch

WXR exports live in `tools/wordpress-converter/exports/`. The three scripts below
take the export path as an optional first argument; with no argument they use the
newest-named XML in that directory. They resolve `_posts/`, `assets/` etc.
relative to the repo root, so they can be run from anywhere.

```sh
cd tools/wordpress-converter

python3 -m venv ../../.venv
../../.venv/bin/pip install markdownify requests lxml

../../.venv/bin/python convert.py             # WXR -> _posts, _pages, _category, _tag
../../.venv/bin/python download_assets.py     # WP attachments (~2.5k images)
../../.venv/bin/python download_referenced.py # WP-generated variants (~1.4k more)
../../.venv/bin/python parse_locations.py     # map CSV -> _data/locations.json
```

## Importing a later WordPress export

Drop the new WXR into `tools/wordpress-converter/exports/`, then, from the repo
root:

```sh
E=tools/wordpress-converter/exports/<file>.xml

.venv/bin/python tools/wordpress-converter/convert.py             "$E"
.venv/bin/python tools/wordpress-converter/download_assets.py     "$E"
.venv/bin/python tools/wordpress-converter/download_referenced.py "$E"

rclone sync assets/wp-content/uploads/YYYY/MM/ \
  r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" --progress
```

`convert.py` only writes items with status `publish` — scheduled (`future`) and
draft posts are skipped, though their attachments still download. Pass
`--include-future` to emit scheduled posts too; Jekyll still won't render them
until a build runs on or after their date.

## What is gitignored

- `assets/wp-content/uploads/` — images (~1.3 GiB, in R2 instead)
- `_data/api_keys.yml` — secrets
- `_site/`, `.jekyll-cache/`, `.jekyll-metadata`, `.bundle/`, `vendor/`
- `.venv/`, `__pycache__/`, `*.pyc`
- `Gemfile.lock`
- `download*.log`, `download*failures.log`

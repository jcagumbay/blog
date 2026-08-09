# code. travel. repeat.

Jekyll photoblog, migrated from WordPress. Deploys to GitHub Pages at
`jcagumbay.github.io/blog`. 216 posts, 6 pages, 585 tags, 2 categories.

## Layout

| Path | What |
|------|------|
| `_posts/` | `YYYY-MM-DD-slug.md`, one per post |
| `_pages/` | About, Travel Tips, Where I've Been, Privacy Policy |
| `_category/`, `_tag/` | **Pre-generated** archive pages, one file per term |
| `_layouts/` | default, home, post, page, archive, map |
| `_data/locations.json` | Map markers. Hand-edited — see below |
| `assets/wp-content/uploads/` | Images. **Gitignored**, they live in R2 |
| `tools/new-post/` | `new_post.py` — the only tool in routine use |
| `tools/wordpress-converter/` | Retired migration scripts + their inputs |

Custom theme, no minima. Jekyll 3.x via the `github-pages` gem. Permalinks are
`/:year/:month/:day/:title/`.

## Traps

These cost real debugging time. None are visible from the code alone.

**Future-dated posts do not publish themselves.** Jekyll's `future` setting is
unset, so it defaults to false and filters them out at *build* time. The
workflow triggers only on `push` and `workflow_dispatch` — there is no cron. A
post dated next month stays invisible until someone runs a build on or after
that date. Currently pending: `_posts/2026-09-08-salzburg-austria.md`.

**Archive pages are pre-generated.** Using a tag with no `_tag/<slug>.md` file
means `/tag/<slug>/` 404s — the tag renders on the post but leads nowhere.
`new_post.py` creates missing archives; if a tag is added by hand, the archive
must be too.

**`_data/locations.json` is the source of truth for the map.** Edit it
directly. `tools/wordpress-converter/parse_locations.py` regenerates it
wholesale from a 164-row CSV and will delete anything added since the
migration. It is retired — only run it after re-exporting the CSV from
WordPress.

**Images are not in the repo.** `assets/wp-content/uploads/` is gitignored
(~1.3 GiB). Post markdown references `/assets/wp-content/...`; CI rewrites
those to the CDN at build time. Local dev serves them off disk, so a locally
working image proves nothing about production — it also has to be in R2.

**The R2 public dev URL is dead.** `pub-3795b62a20fb4711ae001dc9eec6af44.r2.dev`
returns 401 for every object. The live CDN is the custom domain
`https://4e8d99e3.cagumbay.com`, held in the `CDN_URL` repo variable.

**rclone reports a spurious failure on first attempt.** Uploads to R2 throw
`501 NotImplemented` for every file on attempt 1, then succeed on attempt 2.
Not an error — verify with `rclone check` rather than trusting the log.

## Deploy

Push to `main`, or run the workflow manually. `.github/workflows/jekyll.yml`:

1. Writes `_data/api_keys.yml` from the `GOOGLE_MAPS_API_KEY` secret
2. Rewrites `/assets/wp-content/` → `$CDN_URL/wp-content/` across `_posts`,
   `_pages`, `_layouts`, `_includes`, `_config.yml`, `index.html`
3. `bundle exec jekyll build`
4. `actions/deploy-pages`

Manual run: `gh workflow run jekyll.yml --repo jcagumbay/blog`

## Local preview

```sh
docker run -d --rm --name jekyll-preview \
  -v "$PWD:/srv/jekyll" -v jekyll-bundle:/usr/local/bundle \
  -p 4000:4000 jekyll/jekyll:latest \
  jekyll serve --host 0.0.0.0 --watch --incremental
```

http://localhost:4000/ · restart after `_config.yml` changes · needs
`_data/api_keys.yml` (copy from `_data/api_keys.example.yml`) for the map.

One-off build to check output without touching `_site/`:

```sh
docker run --rm -v "$PWD:/srv/jekyll" -v jekyll-bundle:/usr/local/bundle \
  -v /tmp/out:/out jekyll/jekyll:latest jekyll build --destination /out
```

Add `--future` to that to simulate a build after a scheduled post's date.

## Conventions

- Post body is markdown; images are raw `<figure class="wp-caption">` blocks
  with an `<img>` and `<figcaption class="wp-caption-text">`. Kramdown passes
  block-level HTML through. Match the surrounding posts rather than using
  markdown image syntax.
- Front matter carries `image:` (the hero, used by the home tiles and SEO tags).
- `original_url` and `wordpress_id` are migration provenance on old posts. New
  posts don't need them.
- Tags are lowercase and free-form; categories are `Travel` and `Photo Wall`
  only.
- Python tooling runs from `.venv` at the repo root
  (`markdownify`, `requests`, `lxml`).

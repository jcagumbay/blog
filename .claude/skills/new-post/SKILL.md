---
name: new-post
description: Publish a new post on the code.travel.repeat. blog — scaffold the entry, place its images, sync them to R2, add a map marker, and deploy. Use when the user wants to write, add, or publish a blog post, or when they have photos from a trip to turn into a post.
---

# Publishing a post

Six steps. Steps 1-3 are the post; 4-6 make it visible.

## 1. Scaffold

```sh
./tools/new-post/new_post.py "Munich, Germany" --cat Travel --tag munich --tag germany --no-edit
```

Creates `_posts/YYYY-MM-DD-slug.md`, the `assets/wp-content/uploads/YYYY/MM/`
directory, and any missing `_tag/`/`_category/` archive pages. Drop `--no-edit`
to open `$EDITOR`.

Categories are `Travel` or `Photo Wall` — nothing else. Tags are lowercase and
free-form. Only pass `--date` for a backdated or scheduled post; read the
scheduling section below before scheduling one.

## 2. Write the body

Read two or three recent posts in `_posts/` first and match their voice — first
person, conversational, specific. Don't write generic travel copy.

Images are raw HTML, not markdown. Kramdown passes block-level HTML through:

```html
<figure class="wp-caption">
<img class="size-full" src="/assets/wp-content/uploads/2026/08/DSCF0744.jpg" width="1024" height="671" />
<figcaption class="wp-caption-text">Draw me like one of your French sangliers</figcaption>
</figure>
```

Set `image:` in the front matter to the hero — it drives the home page tile and
the SEO tags. Drop the `REPLACE_ME.jpg` placeholders the scaffold leaves behind.

## 3. Place the images

Put files in `assets/wp-content/uploads/YYYY/MM/` matching the post's date.
That directory is gitignored, so the images never enter the repo — R2 serves
them. Verify every `src` resolves before moving on:

```sh
grep -o 'src="/assets[^"]*"' _posts/YYYY-MM-DD-slug.md | sed 's/src="//;s/"//' \
  | while read p; do [ -f ".$p" ] || echo "MISSING $p"; done
```

## 4. Sync to R2

Use the `r2-sync` skill. Short version, for the post's month only:

```sh
rclone copy assets/wp-content/uploads/YYYY/MM/ r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" --progress
rclone check assets/wp-content/uploads/YYYY/MM/ r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ --size-only
```

Attempt 1 throws `501 NotImplemented` for every file and attempt 2 succeeds.
Expected — trust `rclone check`, not the log.

Skipping this step is the most common way to ship a post with broken images:
they work locally off disk and 404 in production.

## 5. Add the map marker

Append to `_data/locations.json` — that file is the source of truth. Never run
`parse_locations.py`; it rebuilds from a stale CSV and deletes hand-added
markers.

Next `id` is the current max plus one. Geocode rather than guessing:

```sh
curl -s -A "blog/1.0" "https://nominatim.openstreetmap.org/search?q=Munich%2C%20Germany&format=json&limit=1"
```

Nominatim returns local-language names (München, Bayern, Deutschland); the file
uses English throughout, so normalise. `url` is the post's permalink,
`/YYYY/MM/DD/slug/`.

```json
{
  "id": 167, "title": "City, Country", "address": "City, Country",
  "lat": 48.1371079, "lng": 11.5753822,
  "city": "City", "state": "Region", "country": "Country",
  "url": "/YYYY/MM/DD/post-slug/", "external_url": null
}
```

A marker whose post isn't published yet is filtered out by `_layouts/map.html`
and appears on its own once the post goes live.

## 6. Verify, then deploy

Build before pushing — it is the only way to catch a Liquid or front-matter
error:

```sh
docker run --rm -v "$PWD:/srv/jekyll" -v jekyll-bundle:/usr/local/bundle \
  -v /tmp/out:/out jekyll/jekyll:latest jekyll build --destination /out
ls -d /tmp/out/YYYY/MM/DD/slug/
```

Then commit `_posts/`, `_tag/`, `_category/`, `_data/locations.json` and push.
CI rewrites `/assets/wp-content/` to the CDN and deploys.

## Scheduling a post

A future `--date` does **not** publish itself. Jekyll's `future` is unset, so
future-dated posts are filtered out at build time, and the workflow runs only
on push and manual dispatch — no cron. The post stays invisible until a build
runs on or after its date:

```sh
gh workflow run jekyll.yml --repo jcagumbay/blog
```

Say this explicitly when scheduling — the user needs a calendar reminder. If
they want it live now instead, either re-date it to today or set `future: true`
in `_config.yml`.

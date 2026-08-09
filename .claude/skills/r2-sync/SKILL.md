---
name: r2-sync
description: Upload or verify blog images in the Cloudflare R2 bucket that serves this site's assets. Use when images 404 in production but work locally, when adding photos to an existing post, or when the user mentions R2, rclone, the CDN, or asset uploads.
---

# R2 asset sync

Images are not in git. `assets/wp-content/uploads/` is gitignored (~1.3 GiB);
R2 serves them and CI rewrites `/assets/wp-content/` to the CDN at build time.
So an image on disk is invisible in production until it is in R2.

- Bucket: `jboy-cagumbay-com`, rclone remote `r2:`
- Public CDN: `https://4e8d99e3.cagumbay.com` (custom domain, in the `CDN_URL`
  repo variable)
- The old `pub-3795b62a20fb4711ae001dc9eec6af44.r2.dev` URL is **dead** — 401
  on every object. Don't test against it and conclude an upload failed.

## Upload

Scope to the month you changed. A full sync walks 1.3 GiB for nothing.

```sh
rclone copy assets/wp-content/uploads/YYYY/MM/ \
  r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ \
  --header-upload "Cache-Control: public, max-age=31536000, immutable" \
  --transfers=8 --checkers=8 --checksum --progress
```

The `Cache-Control` header matters: filenames are immutable, so objects should
be cached for a year. Uploading without it leaves objects with no cache policy.

Prefer `copy` over `sync` — `sync` deletes remote objects with no local
counterpart, and the local tree may be partial.

## The 501 that isn't a failure

Every upload prints this for every file, then succeeds:

```
ERROR : DSCF1572.jpg: Failed to copy: NotImplemented: Not Implemented
        status code: 501
ERROR : Attempt 1/3 failed with 34 errors and: NotImplemented: Not Implemented
ERROR : Attempt 2/3 succeeded
```

R2 rejecting rclone's first-pass checksum path. Attempt 2 goes through. Never
report this as a failed upload — verify instead.

## Verify

```sh
rclone check assets/wp-content/uploads/YYYY/MM/ \
  r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/ --size-only
```

`0 differences found` is the answer. Then confirm public reachability and the
cache header on one object:

```sh
curl -sI "https://4e8d99e3.cagumbay.com/wp-content/uploads/YYYY/MM/FILE.jpg" \
  | grep -iE "^(HTTP|cache-control)"
```

Want `HTTP/2 200` and `cache-control: public, max-age=31536000, immutable`.

## Diagnosing a 404 in production

Work outward:

1. On disk? `ls assets/wp-content/uploads/YYYY/MM/FILE.jpg`
2. In R2? `rclone lsl r2:jboy-cagumbay-com/wp-content/uploads/YYYY/MM/`
3. Public? `curl -sI https://4e8d99e3.cagumbay.com/wp-content/uploads/...`
4. If all three pass, the problem is the build rewrite — check that `CDN_URL`
   is set on the repo and that the reference lives in a file the workflow
   rewrites (`_posts`, `_pages`, `_layouts`, `_includes`, `_config.yml`,
   `index.html`; note `_data/` is **not** rewritten).

Case matters — R2 keys are case-sensitive, `.JPG` and `.jpg` are different
objects.

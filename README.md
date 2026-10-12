digitalmeh.net — a Jekyll site, migrated from WordPress in 2026.

## Running it locally

```bash
bundle install
bundle exec jekyll serve --config _config.yml,_config_preview.yml
```

The `_config_preview.yml` overlay matters: without it the build emits absolute URLs from
`site.url`, so a local preview loads assets from, and links to, the live site.

## Publishing

Push to `main` and it publishes. `deploy-pages.yml` builds and deploys to GitHub Pages.

Posts with photos: drop them in `assets/images/<year>/<month>/`, commit to a branch, and
CI resizes them and commits the result back. Then merge.

## Why posts are `.html`, not Markdown

They were migrated from WordPress as rendered HTML. Running that through kramdown
**silently dropped 27 of 53 images** on one post, because it reparses WordPress's gallery
markup. `.html` files are passed through untouched, which is the whole point of a
migration. New posts can be Markdown.

## Documentation

See [docs/](docs/) — the [migration plan](docs/migration-plan.md), the
[post manifest](docs/post-manifest.csv) and the [taxonomy](docs/taxonomy.md).

# Backup and restore

## What exists

A complete capture of the WordPress site as it stood on **2026-10-09**, taken before any
migration work, and **restore-verified** — the database was loaded into a clean MariaDB
container and every count matched the live site.

| File | Size | Contents |
|---|---|---|
| `bitnami_wordpress.sql.gz` | 1.1 MB | the whole database: all 152 published posts, 84 drafts, 2 private, comments, taxonomy, options |
| `swag.tar.gz` | 1,028 MB | WordPress files and `wp-content/uploads` — 12,619 entries, 3,844 upload files |
| `compose.tar.gz` | 595 B | the Docker Compose definition |
| `npm-proxy-hosts.tar.gz` | 1.2 KB | Nginx Proxy Manager routing |

**Two copies:**

- `phatmyth:/files/data/backups/digitalmeh.net/2026-10-09/`
- `pcloud:backups/digitalmeh.net/2026-10-09/` — the durable one

> ⚠️ `swag.tar.gz` contains `wp-config.php`, which holds database credentials and salts.
> It must never be committed to a repository.

### Refreshing or re-fetching

```bash
# push a local archive up
rclone copy /files/data/backups/digitalmeh.net/2026-10-09 \
            pcloud:backups/digitalmeh.net/2026-10-09 --progress

# pull it back down anywhere rclone is configured
rclone copy pcloud:backups/digitalmeh.net/2026-10-09 ./restore --progress
```

## Restoring one post

The common case: a post in [dropped-posts.md](dropped-posts.md) earns its place after all.
You do **not** need to stand WordPress back up.

**1. Load the database into a throwaway container**

```bash
docker run -d --name wp-restore -e MARIADB_ROOT_PASSWORD=restore \
  -e MARIADB_DATABASE=wp mariadb:11
# wait for it to finish initialising, then:
gunzip -c bitnami_wordpress.sql.gz | docker exec -i wp-restore mariadb -uroot -prestore wp
```

Use the official `mariadb:11` image, **not** `bitnami/mariadb:11.1.4` — that tag has been
pulled from the registry and no longer exists.

**2. Pull the post out**

```sql
SELECT post_title, post_date, post_name, post_content
FROM wp_posts WHERE post_name = 'the-slug';
```

**3. Render it.** `post_content` is raw: WordPress adds paragraphs and expands
`[gallery]` shortcodes at display time, and **only 34 of 152 posts have `<p>` tags stored**.
Running the raw column through a converter produces collapsed prose and literal shortcodes.
The migration avoided this by taking WordPress's *rendered* output from its REST API — which
is no longer possible once the site is gone. For a one-off restore, either hand-fix the
paragraphs or stand the container up with a WordPress image pointed at the restored
database and copy what it renders.

**4. Recover its images**

```bash
tar tzf swag.tar.gz | grep 'uploads/2011/09'          # find them
tar xzf swag.tar.gz --wildcards '*/uploads/2011/09/*' # extract
```

Then place under `assets/images/<year>/<month>/` and run `script/prep-images.sh --apply`.

**5. Write the post** as `_posts/YYYY-MM-DD-slug.html` with `redirect_from` carrying the old
dated permalink, matching the existing files.

## The drafts are worth a look

The archive holds **84 draft posts and 2 private ones** that were never published and that
the public API could not see. Most are stubs — 16 are under 100 characters — but **17 have
more than 500 characters of real content**, spanning 2006 to 2023.

Nobody has read them. They were excluded from the triage wizard, which covered published
posts only. Some may be finished pieces that simply never got the publish button, which
makes them the most interesting unexamined thing in the archive.

```sql
SELECT post_date, post_name, LENGTH(post_content), post_title
FROM wp_posts WHERE post_type='post' AND post_status='draft'
  AND LENGTH(post_content) > 500 ORDER BY post_date;
```

## Reading the unpublished posts

`script/wp-posts.py` reads `wp_posts` straight out of `bitnami_wordpress.sql.gz`, so
inspecting the 84 drafts and 2 private posts needs no MySQL and no restore:

```
script/wp-posts.py --counts                  # posts and pages by status
script/wp-posts.py --list draft --min 500    # the 17 substantive drafts
script/wp-posts.py --list private
script/wp-posts.py --show grim-dragon        # by slug, or by title; hyphens are fine
```

It skips revisions, which otherwise show up as several near-identical copies of the same
draft, and it translates mysqldump's escapes — without that, every `\r\n` in a post body
reads as a literal `rn`.

## Checking a draft for credentials

**One of the drafts carries an NZBGeek API key and a MusicBrainz access token** on labelled
lines. Both were rotated on 2026-10-09, so the strings are dead, and they were never in git
or on the live site — but strip them before publishing that draft anyway.

It is not named here on purpose: this repo is public, and naming it would point straight at
the one draft worth not advertising. Scan instead, which beats trusting a title:

```
script/wp-posts.py --list draft --min 200 \
  | awk '$3 != "(no" {print $3}' \
  | while read slug; do
      script/wp-posts.py --show "$slug" 2>/dev/null \
        | grep -nEi 'api[_ -]?key|token|secret|password|brainzcode|[0-9a-f]{32}' \
        | sed "s|^|$slug: |"
    done
```

The `$3 != "(no"` guard skips drafts that were never saved with a slug; those need
`--show "<part of the title>"` instead. Verified: the scan surfaces all three credential
strings, and also flags two ROM checksums in `SGH-T989 101`, which are benign.

Run that before publishing anything out of the archive. No other unpublished post contains
anything credential-shaped — the 32-hex strings in `SGH-T989 101` are ROM checksums.

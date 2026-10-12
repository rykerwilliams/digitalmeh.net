#!/usr/bin/env python3
"""Read posts straight out of the archived WordPress dump.

The 84 drafts and 2 private posts were never migrated -- they live only in
bitnami_wordpress.sql.gz. This reads that dump without needing MySQL.

  script/wp-posts.py --counts                 posts and pages by status
  script/wp-posts.py --list draft             drafts, longest content first
  script/wp-posts.py --list draft --min 500   only the substantive ones
  script/wp-posts.py --show grim-dragon       one post's content, by slug
  script/wp-posts.py --show grim-dragon --html > /tmp/gd.html

Dump path defaults to the phatmyth archive; override with --dump.
wp_posts has 23 columns: post_content is 5, post_title 6, post_status 8,
post_name 12, post_type 21 (1-indexed).
"""
import argparse, collections, gzip, html, sys

CONTENT, TITLE, STATUS, SLUG, DATE, TYPE, NCOLS = 4, 5, 7, 11, 2, 20, 23

# mysqldump escapes these; appending the literal next character turns \r\n into
# "rn" and silently corrupts every post body.
UNESCAPE = {"0": "\0", "n": "\n", "r": "\r", "t": "\t", "b": "\b",
            "Z": "\x1a", "\\": "\\", "'": "'", '"': '"'}
DEFAULT_DUMP = "/files/data/backups/digitalmeh.net/2026-10-09/bitnami_wordpress.sql.gz"


def rows(sql):
    """Yield each (...) tuple as a list of strings, honoring quotes and backslash escapes."""
    i, n = 0, len(sql)
    while i < n:
        if sql[i] != "(":
            i += 1
            continue
        i += 1
        fields, cur, inq = [], [], False
        while i < n:
            c = sql[i]
            if inq:
                if c == "\\":
                    nxt = sql[i + 1] if i + 1 < n else ""
                    cur.append(UNESCAPE.get(nxt, nxt))
                    i += 2
                elif c == "'":
                    inq = False
                    i += 1
                else:
                    cur.append(c)
                    i += 1
                continue
            if c == "'":
                inq = True
                i += 1
            elif c == ",":
                fields.append("".join(cur))
                cur = []
                i += 1
            elif c == ")":
                fields.append("".join(cur))
                i += 1
                break
            else:
                cur.append(c)
                i += 1
        yield fields


def load(dump):
    txt = gzip.open(dump, "rt", encoding="utf-8", errors="ignore").read()
    try:
        start = txt.index("INSERT INTO `wp_posts` VALUES")
        end = txt.index("UNLOCK TABLES", start)
    except ValueError:
        sys.exit(f"{dump}: no wp_posts data found")
    return [f for f in rows(txt[start:end]) if len(f) == NCOLS]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", default=DEFAULT_DUMP)
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--list", metavar="STATUS")
    ap.add_argument("--show", metavar="SLUG")
    ap.add_argument("--min", type=int, default=0, help="minimum content length")
    ap.add_argument("--html", action="store_true", help="with --show, unescape entities")
    a = ap.parse_args()

    posts = load(a.dump)

    if a.counts:
        c = collections.Counter((f[TYPE], f[STATUS]) for f in posts)
        for (ty, st), k in sorted(c.items(), key=lambda x: -x[1]):
            if ty in ("post", "page"):
                print(f"{ty:<6} {st:<12} {k}")
        return

    if a.list:
        sel = [f for f in posts if f[TYPE] == "post" and f[STATUS] == a.list
               and len(f[CONTENT]) >= a.min]
        for f in sorted(sel, key=lambda f: -len(f[CONTENT])):
            print(f"{len(f[CONTENT]):>7}ch  {f[DATE][:10]}  {f[SLUG] or '(no slug)':<44} {f[TITLE][:56]}")
        print(f"\n{len(sel)} {a.list} posts" + (f" with >= {a.min} chars" if a.min else ""))
        return

    if a.show:
        # Many drafts were never saved with a slug, so match on the title too,
        # treating hyphens and spaces as the same thing.
        def norm(x):
            return x.lower().replace("-", " ").replace("_", " ").strip()
        want = norm(a.show)
        hits = [f for f in posts
                if f[TYPE] in ("post", "page")
                and (f[SLUG] == a.show or want == norm(f[SLUG]) or want in norm(f[TITLE]))]
        if not hits:
            sys.exit(f"no post matching {a.show!r}")
        for f in hits:
            print(f"--- {f[TITLE]} [{f[STATUS]}] {f[DATE]} slug={f[SLUG]} ---\n")
            body = f[CONTENT]
            print(html.unescape(body) if a.html else body)
        return

    ap.print_help()


if __name__ == "__main__":
    main()

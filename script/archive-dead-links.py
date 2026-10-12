#!/usr/bin/env python3
"""Repoint dead outbound links at an Internet Archive snapshot.

Where no snapshot exists, --unlink drops the <a> and keeps its text. That is the
right fallback here because the link text carries the meaning on its own -- a
person's name, a handle, "I even made Top 8" -- so the prose still reads and
nobody is sent to a 404.

Finds the snapshot closest to the date of the post that links it, so a 2018
tournament report gets the forum thread as it looked in 2018, not whatever the
URL became later.

  script/archive-dead-links.py              dry run: show what would change
  script/archive-dead-links.py --apply      rewrite the posts

Links that are blocked rather than dead are skipped by host -- Facebook answers
400 to anything unauthenticated, which says nothing about whether the page is
still there for a signed-in reader.
"""
import argparse, collections, glob, html, json, re, sys, time
import urllib.parse, urllib.request, urllib.error

# The /wayback/available endpoint returns {} for URLs that are definitely
# archived -- it does not normalize www. variants, so a link to
# themanadrain.com missed snapshots filed under www.themanadrain.com. The CDX
# index normalizes via urlkey and lists every capture, so we use that and pick
# the one closest to the post's own date.
CDX = "https://web.archive.org/cdx/search/cdx"
HEADERS = {"User-Agent": "digitalmeh-migration/1.0 (+https://digitalmeh.net/)"}

# Blocked, not rotted: leave these alone.
SKIP_HOSTS = {"www.facebook.com", "facebook.com"}


def posts_and_links():
    """url -> {post path: post date as YYYYMMDD}"""
    out = collections.defaultdict(dict)
    for path in sorted(glob.glob("_posts/*.html")):
        body = open(path, encoding="utf-8").read()
        m = re.search(r"^date:\s*(\d{4})-(\d{2})-(\d{2})", body, re.M)
        date = "".join(m.groups()) if m else "20200101"
        for raw in re.findall(r'href="(https?://[^"]+)"', body):
            out[raw][path] = date
    return out


def snapshot(url, when):
    """Snapshot closest to `when` (YYYYMMDD), or None."""
    q = urllib.parse.urlencode({
        "url": html.unescape(url),
        "output": "json",
        "filter": "statuscode:200",
        "collapse": "digest",
        "limit": "200",
        "fl": "timestamp,original",
    })
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"{CDX}?{q}", headers=HEADERS)
            with urllib.request.urlopen(req, timeout=45) as r:
                rows = json.loads(r.read() or b"[]")
            if len(rows) < 2:
                return None
            target = int(when)
            best = min(rows[1:], key=lambda row: abs(int(row[0][:8]) - target))
            ts, original = best[0], best[1]
            return f"https://web.archive.org/web/{ts}/{original}", ts
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(6 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(4)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--unlink", action="store_true",
                    help="for dead links with no snapshot, keep the text and drop the <a>")
    ap.add_argument("--report", default="docs/link-report.md",
                    help="report to read the dead-link list from")
    a = ap.parse_args()

    dead = []
    for line in open(a.report, encoding="utf-8"):
        m = re.match(r"\|\s*`([^`]+)`\s*\|\s*(https?://\S+?)\s*\|", line)
        if m:
            dead.append((m.group(1), m.group(2)))
    if not dead:
        sys.exit(f"no dead links parsed out of {a.report}")

    links = posts_and_links()
    found, missing, skipped = [], [], []

    for status, url in dead:
        host = urllib.parse.urlparse(html.unescape(url)).netloc.lower()
        if host in SKIP_HOSTS:
            skipped.append((url, "blocked, not dead"))
            continue
        where = links.get(url)
        if not where:
            missing.append((url, "not found in any post (stale report?)"))
            continue
        when = min(where.values())
        got = snapshot(url, when)
        time.sleep(0.8)
        if got:
            found.append((url, got[0], got[1], when, sorted(where)))
            print(f"  {got[1][:8]}  {url[:72]}")
        else:
            missing.append((url, "no snapshot"))
            print(f"  --------  {url[:72]}  NO SNAPSHOT")

    print(f"\n  archived {len(found)}, no snapshot {len(missing)}, skipped {len(skipped)}")
    for u, why in missing:
        print(f"    {why}: {u[:84]}")
    for u, why in skipped:
        print(f"    {why}: {u[:84]}")

    if not a.apply:
        print("\n  dry run; pass --apply to rewrite")
        return 0

    n = 0
    for url, snap, ts, when, paths in found:
        for path in paths:
            s = open(path, encoding="utf-8").read()
            new = s.replace(f'href="{url}"', f'href="{snap}"')
            if new != s:
                open(path, "w", encoding="utf-8").write(new)
                n += 1
    print(f"\n  rewrote {n} hrefs")

    if a.unlink:
        gone = [u for u, why in missing if why == "no snapshot"]
        u_count = 0
        for url in gone:
            for path in links.get(url, {}):
                s = open(path, encoding="utf-8").read()
                # <a ...href="URL"...>TEXT</a>  ->  TEXT
                new = re.sub(r'<a\b[^>]*href="' + re.escape(url) + r'"[^>]*>(.*?)</a>',
                             r"\1", s, flags=re.S)
                if new != s:
                    open(path, "w", encoding="utf-8").write(new)
                    u_count += 1
        print(f"  unlinked {u_count} dead links with no snapshot")
    return 0


if __name__ == "__main__":
    sys.exit(main())

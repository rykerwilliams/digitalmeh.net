#!/usr/bin/env python3
"""Check every site-relative link in the built site, including #anchors.

Run against _site after a build. Catches the two things that rot silently:
a link to a page that no longer exists, and a link to an #anchor that does not
exist on the page it points at -- which is how post tags and categories link to
their sections on /tags/ and /categories/.

It found 89 broken links the first time it ran: every category link on every post
pointed at /categories-mtg instead of /categories/#mtg, because slugify had been
applied to the whole URL string rather than just the category name.

  script/check-internal-links.py          exits 1 if anything is broken
"""
import glob, os, re, sys, urllib.parse
from collections import defaultdict

def site_url():
    """The production url from _config.yml, so absolute self-links count as internal.

    CI builds with the production config, where jekyll-redirect-from, canonical
    and feed links are absolute. Matching only href="/..." checked 999 links in
    CI against 1,199 locally -- the same pages, with 200 self-links unexamined.
    """
    try:
        for line in open("_config.yml", encoding="utf-8"):
            m = re.match(r'^url:\s*"?([^"\s#]+)"?', line)
            if m and m.group(1):
                return m.group(1).rstrip("/")
    except OSError:
        pass
    return ""


SITE = site_url()

pages = glob.glob("_site/**/*.html", recursive=True)
anchors = {}            # page path -> set of ids
for p in pages:
    html = open(p, encoding="utf-8", errors="ignore").read()
    anchors[p] = set(re.findall(r'\sid="([^"]+)"', html))

def resolve(url):
    """Map a site-relative URL to the file on disk that serves it."""
    path = urllib.parse.unquote(url.split("?")[0])
    cand = "_site" + path
    if path.endswith("/"):
        return cand + "index.html"
    if os.path.isfile(cand):
        return cand
    if os.path.isfile(cand + ".html"):
        return cand + ".html"
    return cand + "/index.html" if os.path.isdir(cand) else cand

bad = defaultdict(list)
checked = 0
for p in pages:
    html = open(p, encoding="utf-8", errors="ignore").read()
    hrefs = re.findall(r'href="(/[^"]*)"', html)
    if SITE:
        hrefs += [h[len(SITE):] or "/"
                  for h in re.findall(r'href="([^"]*)"', html)
                  if h.startswith(SITE + "/") or h == SITE]
    for href in hrefs:
        checked += 1
        url, _, frag = href.partition("#")
        if not url:
            continue                      # same-page anchor, skip
        target = resolve(url)
        if not os.path.isfile(target):
            bad[p].append(f"{href}  (no file at {target})")
            continue
        if frag and frag not in anchors.get(target, set()):
            bad[p].append(f"{href}  (no id=\"{frag}\" on that page)")

n = sum(len(v) for v in bad.values())
print(f"checked {checked} internal links across {len(pages)} pages, {n} broken")
for p, items in sorted(bad.items()):
    for i in items[:6]:
        print(f"::error file={p}::{i}")
if n:
    print("::error::Internal links are broken.")
    sys.exit(1)

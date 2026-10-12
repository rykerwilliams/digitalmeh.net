#!/usr/bin/env python3
"""Check every outbound link in the posts and write a report.

Sixteen years of posts accumulate link rot. This finds it.

  script/check-links.py                      check everything, write docs/link-report.md
  script/check-links.py --host deckbox.org   just one host
  script/check-links.py --limit 50           first N distinct URLs (quick smoke test)
  script/check-links.py --out -              report to stdout

Politeness matters here: 2,273 of the links point at deckbox.org, which is the
Magic card-tooltip target. Requests are grouped by host and each host is hit by
one worker at a time with a delay between requests, so no single site sees a
burst. Different hosts are checked in parallel.
"""
import argparse, collections, glob, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, quote
import urllib.request, urllib.error

# Minimal headers get stalled or refused by a surprising number of sites. npr.org
# timed out after 60s with just a User-Agent and answered in 0.6s with these.
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0 Safari/537.36"),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "identity",
    "Connection": "close",
}


class Redirects(urllib.request.HTTPRedirectHandler):
    """Follow 308 as well.

    urllib's handler knows 301/302/303/307 but not 308, so any site answering a
    permanent http->https redirect with 308 reads as dead. surpasshosting.com and
    npr.org were both reported dead for exactly this reason and are fine.
    """
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_301(req, fp, 301, msg, headers)


OPENER = urllib.request.build_opener(Redirects)


def wire(url):
    """Percent-encode a URL for the request.

    The Magic card-tooltip plugin wrote links as /mtg/Force of Will, with literal
    spaces. Browsers encode those on the fly; urllib sends a malformed request
    line and the server rejects it. 337 of the 550 distinct URLs need this.
    """
    p = urlparse(url)
    path = quote(p.path, safe="/%:@&=+$,~!*'()")
    out = f"{p.scheme}://{p.netloc}{path}"
    if p.query:
        out += "?" + quote(p.query, safe="/%:@&=+$,~!*'()?[]")
    if p.fragment:
        out += "#" + p.fragment
    return out
TIMEOUT = 20
PER_HOST_DELAY = 0.6     # seconds between requests to the same host

# Hosts that rate-limit. web.archive.org answers 429 after a dozen quick
# requests, which reads as a wall of dead links when it is only impatience --
# every one of those URLs returns 200 when asked slowly.
SLOW_HOSTS = {"web.archive.org": 6.0, "archive.org": 6.0}

# Left out of the routine report unless asked for. Both are generated links whose
# targets are verified where they are created -- card links by check-cards.py,
# archive snapshots by archive-dead-links.py -- and both rate-limit hard enough
# that including them fills the report with 429s that are not failures.
DEFAULT_SKIP = ("scryfall.com", "web.archive.org")

# Hosts that refuse automated requests but serve real readers fine. Facebook
# answers 400 to anything unauthenticated; the page below was confirmed live in a
# browser on 2026-10-09. Reported separately rather than as dead, so one
# permanent false positive does not sit at the top of every future report.
BLOCKED = {
    "https://www.facebook.com/DanielAltersMagic/":
        "Facebook 400s unauthenticated requests; confirmed live in a browser 2026-10-09",
}
MAX_HOSTS_PARALLEL = 8

print_lock = threading.Lock()


def collect(pattern="_posts/*.html"):
    """url -> {post basename: count}"""
    links = collections.defaultdict(collections.Counter)
    for path in sorted(glob.glob(pattern)):
        name = path.split("/")[-1]
        body = open(path, encoding="utf-8", errors="ignore").read()
        for u in re.findall(r'href="(https?://[^"]+)"', body):
            links[u][name] += 1
    return links


def check(url, retry=True):
    """Return (status, note). status is an int, or a string for transport errors."""
    req = urllib.request.Request(wire(url), method="HEAD", headers=HEADERS)
    try:
        with OPENER.open(req, timeout=TIMEOUT) as r:
            return r.status, final_note(url, r.geturl())
    except urllib.error.HTTPError as e:
        # Plenty of sites refuse HEAD but serve GET. Retry before believing it.
        if e.code in (400, 403, 405, 406, 409, 501):
            return check_get(url)
        if e.code in (429, 503) and retry:
            time.sleep(12)
            return check(url, retry=False)
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        # A HEAD can time out, or be refused, on a server that answers GET fine.
        # TimeoutError is not a URLError subclass, so it needs naming explicitly.
        reason = str(getattr(e, "reason", e))[:70]
        status, note = check_get(url, timeout=TIMEOUT * 3)
        if isinstance(status, int):
            return status, note
        return "unreachable", reason
    except Exception as e:                      # bad redirects, TLS
        return type(e).__name__, str(e)[:70]


def check_get(url, timeout=TIMEOUT):
    req = urllib.request.Request(wire(url), headers=HEADERS)
    try:
        with OPENER.open(req, timeout=timeout) as r:
            r.read(2048)
            return r.status, final_note(url, r.geturl())
    except urllib.error.HTTPError as e:
        return e.code, ""
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return "unreachable", str(getattr(e, "reason", e))[:70]
    except Exception as e:
        return type(e).__name__, str(e)[:70]


# deckbox does not 404 an unknown card. It 302s to its generic card index, so a
# misspelled card name looks alive to any checker that only reads status codes.
# Treat that specific landing page as "card not found".
DECKBOX_MISS = "/games/mtg/cards"


def is_miss(url, final):
    return "deckbox.org" in urlparse(url).netloc.lower() and final.rstrip("/").endswith(DECKBOX_MISS)


def final_note(url, final):
    if final.rstrip("/") != wire(url).rstrip("/"):
        return "-> " + final
    return ""


def run(links, verbose=True):
    by_host = collections.defaultdict(list)
    for u in links:
        by_host[urlparse(u).netloc.lower()].append(u)

    results = {}
    done = [0]
    total = len(links)

    def do_host(host):
        delay = SLOW_HOSTS.get(host, PER_HOST_DELAY)
        for u in sorted(by_host[host]):
            status, note = check(u)
            results[u] = (status, note)
            done[0] += 1
            if verbose:
                with print_lock:
                    bad = not (isinstance(status, int) and 200 <= status < 300)
                    if bad or note:
                        print(f"  [{done[0]:>4}/{total}] {status}  {u}  {note}", file=sys.stderr)
                    elif done[0] % 50 == 0:
                        print(f"  [{done[0]:>4}/{total}] …", file=sys.stderr)
            time.sleep(delay)

    with ThreadPoolExecutor(max_workers=MAX_HOSTS_PARALLEL) as ex:
        list(ex.map(do_host, sorted(by_host, key=lambda h: -len(by_host[h]))))
    return results


def report(links, results, skipped_hosts=()):
    ok, redirected, dead, blocked = [], [], [], []
    for u, (status, note) in sorted(results.items()):
        row = (u, status, note, sorted(links[u]))
        if u in BLOCKED:
            blocked.append((u, BLOCKED[u], sorted(links[u])))
            continue
        if isinstance(status, int) and 200 <= status < 300:
            if note.startswith("-> ") and is_miss(u, note[3:]):
                dead.append((u, "card not found", note, sorted(links[u])))
            elif note and "?printing=" in note:
                ok.append(row)        # deckbox always adds a printing id; not a real move
            else:
                (redirected if note else ok).append(row)
        else:
            dead.append(row)

    refs = sum(sum(links[u].values()) for u in links)
    out = []
    w = out.append
    w("# Outbound link report\n")
    w(f"Checked **{len(results)} distinct URLs** ({refs} references) across "
      f"{len(glob.glob('_posts/*.html'))} posts.\n")
    if skipped_hosts:
        w(f"Not checked here: {', '.join('`' + h + '`' for h in skipped_hosts)}. Those are "
          "generated links, verified where they are generated — card names by "
          "`check-cards.py`, archive snapshots by `archive-dead-links.py` — and both hosts "
          "rate-limit hard enough that including them fills this table with 429s that are "
          "not failures. Pass `--no-skip` to check them anyway.\n")
    w(f"| | count |\n|---|---|")
    w(f"| alive | {len(ok)} |")
    w(f"| alive, but redirected | {len(redirected)} |")
    w(f"| **dead or unreachable** | **{len(dead)}** |")
    if blocked:
        w(f"| blocked to robots, verified live by hand | {len(blocked)} |")
    w("")

    if blocked:
        w("## Blocked to automated checks, not dead\n")
        w("| url | why | posts |")
        w("|---|---|---|")
        for u, why, posts in blocked:
            w(f"| {u} | {why} | {', '.join(p.replace('.html','') for p in posts[:3])}"
              f"{' …' if len(posts) > 3 else ''} |")
        w("")

    misses = [r for r in dead if r[1] == "card not found"]
    if misses:
        w("## Card names deckbox does not recognise\n")
        w(f"These **{len(misses)}** return HTTP 200, so a status-code check calls them "
          "alive. deckbox 302s an unknown card to its generic index instead of 404ing, "
          "so each of these is a misspelled or renamed card name and the link goes "
          "nowhere useful.\n")
        w("| url | posts |")
        w("|---|---|")
        for u, s_, n, posts in misses:
            w(f"| {u} | {', '.join(p.replace('.html','') for p in posts[:3])}"
              f"{' …' if len(posts) > 3 else ''} |")
        w("")
        dead = [r for r in dead if r[1] != "card not found"]

    if dead:
        w("## Dead or unreachable\n")
        w("| status | url | posts | note |")
        w("|---|---|---|---|")
        for u, s, n, posts in sorted(dead, key=lambda r: str(r[1])):
            w(f"| `{s}` | {u} | {', '.join(p.replace('.html','') for p in posts[:3])}"
              f"{' …' if len(posts) > 3 else ''} | {n} |")
        w("")

    if redirected:
        w("## Redirected (still resolve, but the target moved)\n")
        w("| url | goes to | posts |")
        w("|---|---|---|")
        for u, s, n, posts in redirected:
            w(f"| {u} | {n[3:]} | {', '.join(p.replace('.html','') for p in posts[:2])}"
              f"{' …' if len(posts) > 2 else ''} |")
        w("")

    hosts = collections.Counter(urlparse(u).netloc.lower() for u in results)
    badhosts = collections.Counter(urlparse(r[0]).netloc.lower() for r in dead)
    w("## By host\n")
    w("| host | distinct urls | dead |")
    w("|---|---|---|")
    for h, n in hosts.most_common():
        w(f"| {h} | {n} | {badhosts.get(h, 0)} |")
    w("")
    return "\n".join(out), len(dead)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host")
    ap.add_argument("--skip-host", action="append", default=None,
                    help=f"host to leave out (default: {', '.join(DEFAULT_SKIP)})")
    ap.add_argument("--no-skip", action="store_true",
                    help="check the default-skipped hosts too; expect 429s")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default="docs/link-report.md")
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    links = collect()
    if a.host:
        links = {u: v for u, v in links.items() if a.host in urlparse(u).netloc.lower()}
    skips = [] if a.no_skip else (a.skip_host if a.skip_host is not None else list(DEFAULT_SKIP))
    for skip in skips:
        links = {u: v for u, v in links.items() if skip not in urlparse(u).netloc.lower()}
    if a.limit:
        links = dict(sorted(links.items())[:a.limit])
    if not links:
        sys.exit("no links matched")

    print(f"checking {len(links)} distinct URLs…", file=sys.stderr)
    results = run(links, verbose=not a.quiet)
    text, dead = report(links, results, skips)

    if a.out == "-":
        print(text)
    else:
        open(a.out, "w", encoding="utf-8").write(text)
        print(f"wrote {a.out}: {dead} dead of {len(results)}", file=sys.stderr)


if __name__ == "__main__":
    main()

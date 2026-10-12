#!/usr/bin/env python3
"""Verify every Magic card name linked in the posts against Scryfall.

Card links are generated from the name in data-cardname. If the name is wrong,
scryfall.com/search?q=<name> 404s and the link goes nowhere -- which is how the
migrated posts arrived, carrying names like "MoxPearl" and "Dig-Through Time".

  script/check-cards.py              check every distinct name
  script/check-cards.py --delay 0.5  slower, if Scryfall is rate-limiting

Scryfall asks for no more than ~10 requests a second and returns 429 when it has
had enough. Requests that stay 429 after every retry are reported as INCONCLUSIVE
rather than silently dropped -- an earlier version of this script dropped 46 of
409 names that way, and the run looked clean.
"""
import argparse, collections, glob, html, json, re, sys, time
import urllib.parse, urllib.request, urllib.error

UA = {"User-Agent": "digitalmeh-linkcheck/1.0 (+https://digitalmeh.net/)",
      "Accept": "application/json"}


def collect():
    names = collections.Counter()
    where = collections.defaultdict(set)
    for path in sorted(glob.glob("_posts/*.html")):
        post = path.split("/")[-1].replace(".html", "")
        for m in re.finditer(r'data-cardname="([^"]+)"', open(path, encoding="utf-8").read()):
            n = html.unescape(m.group(1))
            names[n] += 1
            where[n].add(post)
    return names, where


def lookup(name, retries=5):
    """Return ('ok', canonical) | ('wrong', canonical) | ('missing', detail) | ('429', '')"""
    url = "https://api.scryfall.com/cards/named?fuzzy=" + urllib.parse.quote(name)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=25) as r:
                got = json.loads(r.read()).get("name", "")
            if got.lower() == name.lower():
                return "ok", got
            return "wrong", got
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(4 * (attempt + 1))
                continue
            if e.code == 404:
                return "missing", "no card of that name"
            return "missing", f"HTTP {e.code}"
        except Exception as e:
            return "missing", type(e).__name__
    return "429", ""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=float, default=0.3)
    a = ap.parse_args()

    names, where = collect()
    print(f"checking {len(names)} distinct card names…", file=sys.stderr)

    wrong, missing, stuck, ok = [], [], [], 0
    for i, n in enumerate(sorted(names), 1):
        kind, detail = lookup(n)
        if kind == "ok":
            ok += 1
        elif kind == "wrong":
            wrong.append((n, detail))
        elif kind == "missing":
            missing.append((n, detail))
        else:
            stuck.append(n)
        time.sleep(a.delay)
        if i % 80 == 0:
            print(f"  …{i}/{len(names)}", file=sys.stderr, flush=True)

    print(f"\n  exact        {ok}")
    print(f"  wrong name   {len(wrong)}")
    print(f"  not a card   {len(missing)}")
    print(f"  INCONCLUSIVE {len(stuck)}  (rate-limited; re-run with --delay 0.6)")
    accounted = ok + len(wrong) + len(missing) + len(stuck)
    assert accounted == len(names), f"only accounted for {accounted} of {len(names)}"

    for n, c in wrong:
        print(f"\n  {n!r}\n      scryfall says -> {c!r}   ({names[n]} links, {len(where[n])} posts)")
    for n, d in missing:
        print(f"\n  {n!r}\n      {d}   ({names[n]} links, {len(where[n])} posts)")
    for n in stuck:
        print(f"\n  {n!r}\n      inconclusive")

    return 1 if (wrong or missing) else 0


if __name__ == "__main__":
    sys.exit(main())

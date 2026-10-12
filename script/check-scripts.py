#!/usr/bin/env python3
"""Check that no inline <script> in the built site has been corrupted.

The mtg_autocard plugin rewrites <<Card>> and ((Card)) into links. Ordinary
JavaScript is full of both shapes -- the search page contains

    var out = esc((from ? '...' : '') + text.slice(from, to) ...)

and the plugin turned that into an <a> tag mid-expression, which made
search.html a syntax error and silently broke search on the live site. The
plugin now skips script/style/pre/code; this makes sure it stays that way.

Also parses every inline script with node when available, so a syntax error
from any cause fails the build rather than reaching a reader.
"""
import glob, os, re, shutil, subprocess, sys, tempfile

MARKERS = ('class="card-link"', "<a href=", "</a>")


def inline_scripts(html):
    for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", html, re.S | re.I):
        attrs, body = m.group(1), m.group(2)
        if "src=" in attrs:            # external file, nothing inline to check
            continue
        if re.search(r'type="(application/ld\+json|application/json)"', attrs, re.I):
            continue                   # data, not code
        yield body


def main():
    pages = glob.glob("_site/**/*.html", recursive=True)
    node = shutil.which("node")
    injected, broken, checked = [], [], 0

    for p in pages:
        html = open(p, encoding="utf-8", errors="ignore").read()
        for body in inline_scripts(html):
            checked += 1
            if any(mk in body for mk in MARKERS):
                injected.append(p)
                continue
            if node:
                with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as f:
                    f.write(body)
                    tmp = f.name
                r = subprocess.run([node, "--check", tmp], capture_output=True, text=True)
                os.unlink(tmp)
                if r.returncode != 0:
                    first = (r.stderr.strip().splitlines() or ["?"])[-1]
                    broken.append((p, first[:120]))

    print(f"checked {checked} inline script(s) across {len(pages)} pages")
    for p in sorted(set(injected)):
        print(f"::error file={p}::an <a> tag was injected into a <script> block "
              f"-- the card-link plugin rewrote JavaScript")
    for p, err in broken:
        print(f"::error file={p}::inline script does not parse: {err}")

    if injected or broken:
        print("::error::Inline JavaScript is corrupted; the page will not work.")
        return 1
    if not node:
        print("note: node not found, only checked for injected markup")
    return 0


if __name__ == "__main__":
    sys.exit(main())

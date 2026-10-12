#!/usr/bin/env bash
# Build (and optionally serve) the site in a container, so no Ruby is needed on the host.
#
#   script/build.sh              build to _site with the production config
#   script/build.sh --preview    build with _config_preview.yml (relative URLs, for local review)
#   script/build.sh --serve      build with the preview config and serve it on $PORT (default 8094)
#
# Gems live in vendor/bundle (gitignored). BUNDLE_PATH must be passed explicitly:
# a container-local `bundle config` does not survive to the next run.
set -uo pipefail
cd "$(dirname "$0")/.."

IMAGE=ruby:3.2
PORT="${PORT:-8094}"
CONFIG=_config.yml
DEST=_site
SERVE=0

for arg in "$@"; do
  case "$arg" in
    --preview) CONFIG=_config.yml,_config_preview.yml ;;
    --serve)   CONFIG=_config.yml,_config_preview.yml; SERVE=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

run() {
  docker run --rm -v "$PWD":/srv -w /srv -u "$(id -u):$(id -g)" \
    -e HOME=/tmp -e BUNDLE_PATH=/srv/vendor/bundle "${EXTRA[@]}" "$IMAGE" bash -lc "$1"
}

EXTRA=()
if ! compgen -G 'vendor/bundle/ruby/*/bin/jekyll' >/dev/null; then
  echo "==> installing gems into vendor/bundle (first run only)"
  run 'bundle install' || exit 1
fi

if [ "$SERVE" = 1 ]; then
  # Bind 0.0.0.0 so the preview is reachable over SSH/LAN, not just inside the container.
  EXTRA=(-p "$PORT:$PORT")
  echo "==> serving on http://0.0.0.0:$PORT/ (ctrl-c to stop)"
  run "bundle exec jekyll serve --config $CONFIG --host 0.0.0.0 --port $PORT"
else
  echo "==> building $CONFIG -> $DEST"
  run "bundle exec jekyll build --config $CONFIG -d $DEST" || exit 1
  echo "==> done: $DEST"
fi

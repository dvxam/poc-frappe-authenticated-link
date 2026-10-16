#!/usr/bin/env bash
# =============================================================================
# Scaffolds an OWNED Backstage app into ./backstage/ (one-time).
#
# The host has no Node/yarn, so @backstage/create-app runs inside a Node
# container. We build/run the app from source afterwards (see backstage/Dockerfile
# and the `backstage` service in docker-compose.yml) — this script only generates
# the monorepo once.
#
# create-app is interactive (a single "app name" prompt, no flag), so we feed the
# name over stdin. The app name "backstage" makes it create the ./backstage/ folder.
#
# Usage:
#   ./scaffold-backstage.sh          # generates ./backstage/
#
# Re-run safety: aborts if ./backstage/ already exists (create-app would fail and
# we never want to clobber an app you've customized).
# =============================================================================
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
NODE_IMAGE="${NODE_IMAGE:-node:24-trixie-slim}" # must match backstage/Dockerfile

if [ -e "$HERE/backstage" ]; then
  echo "!! ./backstage already exists — refusing to overwrite." >&2
  echo "   Remove it first if you really want to re-scaffold." >&2
  exit 1
fi

echo ">> scaffolding Backstage into ./backstage (via $NODE_IMAGE) ..."
# Flow (order matters):
#   1. create-app --skip-install  : scaffold WITHOUT installing. We skip the
#      install here on purpose so we can inject the fix below before any install
#      runs (create-app's own install would otherwise hit the bug and abort).
#   2. inject the `got` resolution : workaround for yarnpkg/berry#7281 —
#      @yarnpkg/core 4.9.2 (pulled in by @backstage/cli) declares `got` via the
#      patch: protocol but ships no patch file, so install dies with
#      "got-npm-11.8.2-*.patch: ENOENT". Forcing plain got bypasses it. Remove
#      once the upstream issue is fixed.
#   3. yarn install                : now succeeds, producing a real, committable
#      yarn.lock the Docker build reproduces with `--immutable`. (node_modules is
#      gitignored and excluded from the Docker build context.)
# We chown back to the host user afterwards (container writes as root).
docker run --rm \
  -v "$HERE":/work -w /work \
  -e CI=1 \
  "$NODE_IMAGE" bash -lc '
    set -e
    corepack enable
    echo "backstage" | npx --yes @backstage/create-app@latest --skip-install
    node -e "const f=\"backstage/package.json\",fs=require(\"fs\");const p=JSON.parse(fs.readFileSync(f));p.resolutions={...(p.resolutions||{}),got:\"npm:11.8.5\"};fs.writeFileSync(f,JSON.stringify(p,null,2)+\"\n\")"
    cd backstage && yarn install && cd ..
    chown -R '"$(id -u)":"$(id -g)"' /work/backstage
  '

echo
echo ">> OK — app generated in ./backstage/"
echo ">> Next: build & run it with the stack:"
echo "     docker compose up -d --build backstage"
echo "     docker compose logs -f backstage      # wait for 'listening on :7007'"
echo "     open http://localhost:${BACKSTAGE_PORT:-7007}  (sign in as guest)"

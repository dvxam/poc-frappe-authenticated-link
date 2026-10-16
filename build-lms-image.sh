#!/usr/bin/env bash
# =============================================================================
# Builds a Frappe image with the `lms` app baked in, via frappe_docker.
# Official method (apps.json passed as a BuildKit secret):
#   https://github.com/frappe/frappe_docker/blob/main/docs/02-setup/02-build-setup.md
#
# Result: local image `vidi-lms:latest` -> set it in .env (FRAPPE_IMAGE).
#
# Usage:
#   ./build-lms-image.sh
#   FRAPPE_BRANCH=version-15 LMS_BRANCH=version-15 ./build-lms-image.sh   # override
# =============================================================================
set -euo pipefail

FRAPPE_BRANCH="${FRAPPE_BRANCH:-version-16}" # frappe_docker doc default
LMS_BRANCH="${LMS_BRANCH:-version-16}"
PAYMENTS_BRANCH="${PAYMENTS_BRANCH:-version-16}" # MANDATORY dependency of lms
IMAGE_TAG="${IMAGE_TAG:-vidi-lms:latest}"
WORKDIR="$(mktemp -d)"

echo ">> cloning frappe_docker into $WORKDIR"
git clone --depth 1 https://github.com/frappe/frappe_docker "$WORKDIR/frappe_docker"
cd "$WORKDIR/frappe_docker"

# apps.json: apps to ADD on top of frappe (frappe is already the base).
# Do NOT include frappe here. Add your custom plugins/courses to this list.
# payments is a mandatory dependency of lms (required_apps) -> required for the
# install even if we don't use the payment features.
cat >apps.json <<JSON
[
  { "url": "https://github.com/frappe/payments", "branch": "${PAYMENTS_BRANCH}" },
  { "url": "https://github.com/frappe/lms", "branch": "${LMS_BRANCH}" }
]
JSON

echo ">> building $IMAGE_TAG (frappe=$FRAPPE_BRANCH, lms=$LMS_BRANCH, payments=$PAYMENTS_BRANCH)"
# apps.json passed via --secret (never --build-arg: it would stay in the history).
# CACHE_BUST: secrets are NOT part of the BuildKit cache key; without it the
# `bench init` layer would be reused and lms would never get installed.
DOCKER_BUILDKIT=1 docker build \
  --progress=plain \
  --build-arg=FRAPPE_PATH=https://github.com/frappe/frappe \
  --build-arg=FRAPPE_BRANCH="$FRAPPE_BRANCH" \
  --build-arg=CACHE_BUST="$(date +%s)" \
  --secret=id=apps_json,src=apps.json \
  --tag="$IMAGE_TAG" \
  --file=images/layered/Containerfile \
  .

cd - >/dev/null
rm -rf "$WORKDIR"

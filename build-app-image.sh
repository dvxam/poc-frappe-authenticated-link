#!/usr/bin/env bash
# =============================================================================
# Builds the LMS image + custom `vidi_integration` app (overlay on vidi-lms:latest).
#
# Prerequisite: the base image must exist (./build-lms-image.sh).
# Result: image `vidi-lms:latest` (by default we overwrite the base tag with the
#         overlay, so .env/compose need no changes).
#
# Usage:
#   ./build-lms-image.sh      # 1. base (frappe + lms + payments)
#   ./build-app-image.sh      # 2. overlay (+ vidi_integration)
# =============================================================================
set -euo pipefail

BASE_IMAGE="${BASE_IMAGE:-vidi-lms:latest}"
OUTPUT_TAG="${OUTPUT_TAG:-vidi-lms:latest}"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo ">> building $OUTPUT_TAG (base=$BASE_IMAGE + app vidi_integration)"
docker build \
  --build-arg=BASE_IMAGE="$BASE_IMAGE" \
  --tag="$OUTPUT_TAG" \
  --file="$HERE/frappe-apps/Dockerfile" \
  "$HERE/frappe-apps"

echo
echo ">> OK. Verify the app is importable:"
echo "   docker run --rm --entrypoint bash $OUTPUT_TAG -lc 'ls -1 apps; python -c \"import vidi_integration\"'"
echo ">> Then install it on the site:"
echo "   docker compose up -d && docker compose run --rm frappe-install-app"

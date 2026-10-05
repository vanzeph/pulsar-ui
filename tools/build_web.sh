#!/usr/bin/env bash
# Build the web dashboard into package resources.
#
# Reproducible delivery form (U2 decision): the Vite build output is
# COMMITTED under src/pulsar_ui/static/ so the Python package hosts the
# dashboard without a Node toolchain at install time. web/package-lock.json
# pins the toolchain; this script regenerates the committed assets:
#
#   tools/build_web.sh          # npm ci + build into src/pulsar_ui/static
#
# CI re-runs the same script as a buildability gate. See README (前端构建).
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root/web"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to build the web dashboard" >&2
  exit 1
fi

npm ci
npm run build   # vite build -> ../src/pulsar_ui/static (see vite.config.ts)

echo
echo "built assets:"
ls -l "$root/src/pulsar_ui/static"

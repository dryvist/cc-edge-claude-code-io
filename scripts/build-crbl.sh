#!/usr/bin/env bash
#
# Build a Cribl pack .crbl tarball from the current repo's pack contents.
#
# Inputs (env vars):
#   REPO_NAME        — pack repo name (used in tarball filename); usually $GITHUB_REPOSITORY's name
#   TAG_NAME         — tag/version to embed in versioned filename; defaults to $GITHUB_REF_NAME
#   ADDITIONAL_FILES — optional space-separated extra files to include
#
# Outputs (written via $GITHUB_ENV when run in a GitHub Actions step):
#   OUT_VERSIONED — /tmp/<repo>-<tag>.crbl
#   OUT_LATEST    — /tmp/<repo>.crbl
#
# Standalone usage (outside CI):
#   REPO_NAME=cc-edge-foo TAG_NAME=v1.2.3 ./scripts/build-crbl.sh

set -euo pipefail

: "${REPO_NAME:?REPO_NAME env var required}"
: "${TAG_NAME:=${GITHUB_REF_NAME:-}}"

if [[ -z "${TAG_NAME}" ]]; then
  echo "::error::TAG_NAME (or GITHUB_REF_NAME) must be set" >&2
  exit 1
fi

OUT_VERSIONED="/tmp/${REPO_NAME}-${TAG_NAME}.crbl"
OUT_LATEST="/tmp/${REPO_NAME}.crbl"

# Standard pack contents (criblpacks convention).
INCLUDE=(data default package.json README.md)
[[ -f LICENSE ]] && INCLUDE+=(LICENSE)
for extra in ${ADDITIONAL_FILES:-}; do
  [[ -e "${extra}" ]] && INCLUDE+=("${extra}")
done

tar -czf "${OUT_VERSIONED}" "${INCLUDE[@]}"
cp "${OUT_VERSIONED}" "${OUT_LATEST}"
ls -lh "${OUT_VERSIONED}" "${OUT_LATEST}"

# Export for downstream GH Actions steps when in CI.
if [[ -n "${GITHUB_ENV:-}" ]]; then
  {
    echo "OUT_VERSIONED=${OUT_VERSIONED}"
    echo "OUT_LATEST=${OUT_LATEST}"
  } >> "${GITHUB_ENV}"
fi

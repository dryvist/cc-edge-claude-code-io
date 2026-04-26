#!/usr/bin/env bash
#
# Structural validation for a dryvist Cribl pack repo. Combines the checks
# that previously lived inline in the cribl-pack-test.yml validate job.
#
# Inputs (env var):
#   PACK_TYPE — 'edge' or 'stream' (required)
#
# Tooling required on PATH: jq, yq (mikefarah).
#
# Emits GitHub Actions error/warning annotations + exits non-zero if any
# blocking check fails. Warnings do not block.

set -euo pipefail

: "${PACK_TYPE:?PACK_TYPE env var must be 'edge' or 'stream'}"

if [[ "${PACK_TYPE}" != "edge" && "${PACK_TYPE}" != "stream" ]]; then
  echo "::error::pack_type must be 'edge' or 'stream', got '${PACK_TYPE}'"
  exit 1
fi

failures=0

# 1) Required files exist at the pack root.
required_files=(package.json default/pack.yml default/pipelines/route.yml README.md)
for f in "${required_files[@]}"; do
  if [[ ! -f "${f}" ]]; then
    echo "::error file=${f}::Required pack file missing"
    failures=$((failures + 1))
  fi
done

# 2) package.json shape — name, version, minLogStreamVersion present.
name=$(jq -r '.name // ""' package.json)
version=$(jq -r '.version // ""' package.json)
minLogStreamVersion=$(jq -r '.minLogStreamVersion // ""' package.json)

for v in name version minLogStreamVersion; do
  if [[ -z "${!v}" || "${!v}" == "null" ]]; then
    echo "::error file=package.json::Missing required field '${v}'"
    failures=$((failures + 1))
  fi
done

# 2a) Pack name follows the cc-{edge,stream}-<source>-io convention (warning only).
expected_prefix="cc-${PACK_TYPE}-"
expected_suffix="-io"
if [[ "${name}" != "${expected_prefix}"*"${expected_suffix}" ]]; then
  echo "::warning file=package.json::Pack name '${name}' does not follow '${expected_prefix}<source>${expected_suffix}' convention"
fi

echo "package.json: name=${name} version=${version} minLogStreamVersion=${minLogStreamVersion}"

# 3) Every route's pipeline reference resolves to a default/pipelines/<name>/conf.yml file.
mapfile -t pipelines_in_routes < <(yq -r '.routes[].pipeline' default/pipelines/route.yml | sort -u)
for pipeline in "${pipelines_in_routes[@]}"; do
  if [[ -z "${pipeline}" || "${pipeline}" == "null" ]]; then continue; fi
  conf="default/pipelines/${pipeline}/conf.yml"
  if [[ ! -f "${conf}" ]]; then
    echo "::error::Route references pipeline '${pipeline}' but ${conf} does not exist"
    failures=$((failures + 1))
  fi
done

# 4) Routes use 'output: __group' (validator rule, warning only).
bad_outputs=$(yq -r '.routes[] | select(.output != "__group") | .id' default/pipelines/route.yml)
if [[ -n "${bad_outputs}" ]]; then
  echo "::warning::These routes do not use 'output: __group' (validator rule): ${bad_outputs}"
fi

# 5) Sample events exist (warning only — packs may legitimately ship without samples).
if [[ -d data/samples ]]; then
  count=$(find data/samples -maxdepth 1 -name '*.json' -type f | wc -l | tr -d ' ')
  if [[ "${count}" -eq 0 ]]; then
    echo "::warning::data/samples/ exists but contains no JSON sample events"
  else
    echo "Found ${count} sample event file(s) in data/samples/"
  fi
else
  echo "::warning::data/samples/ does not exist — pack lacks sample events"
fi

if [[ "${failures}" -gt 0 ]]; then
  echo "::error::Pack structure validation failed (${failures} blocking error(s))"
  exit 1
fi
echo "Pack structure validation passed."

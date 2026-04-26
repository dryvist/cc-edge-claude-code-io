## What this repo is

Cribl Edge pack scaffolded from
[`dryvist/cc-edge-pack-template`](https://github.com/dryvist/cc-edge-pack-template).
Eventual purpose: collect Claude Code telemetry (session JSONL transcripts +
OpenTelemetry metrics) and forward to a Cribl Stream worker group.

## Current state

Ships only the template's demo passthrough pipeline + fixture so the
inherited Vitest harness has something to run end-to-end. Real
`claude-code-otel` and `claude-code-session-logs` pipelines (with eval
functions, real fixtures, captured samples) land in subsequent PRs.

## Sources of truth

| Layer | Where |
|---|---|
| Org-wide policy (TS-everywhere, Biome, Vitest, secrets, releases) | [`dryvist/.github`](https://github.com/dryvist/.github) |
| Test harness mechanics, file boundary, validator rules | [`dryvist/cc-edge-pack-template/docs/`](https://github.com/dryvist/cc-edge-pack-template/tree/main/docs) |

## Top-level rules

- Don't modify generic files here — open a PR against the template repo and let it propagate.
- Don't tag versions; release-please proposes them via PR.
- Don't write inline scripts in workflows — extract to `scripts/*.sh` or use a community action.

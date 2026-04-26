# CLAUDE.md — guidance for AI assistants working in this repo

This file is read by Claude Code on every session. It scopes AI behavior for the
**`cc-edge-claude-code-io`** Cribl Edge pack.

For the canonical org-wide policy and tooling baseline (TypeScript everywhere,
Biome, Vitest, nix-devenv shell, release-please inheritance), read
[`dryvist/.github/CLAUDE.md`](https://github.com/dryvist/.github/blob/main/CLAUDE.md).

For the template-level "generic vs pack-specific" boundary, read
[`dryvist/cc-edge-pack-template/CLAUDE.md`](https://github.com/dryvist/cc-edge-pack-template/blob/main/CLAUDE.md).

## Repository scope

Cribl Edge pack that collects Claude Code telemetry and forwards it to a Cribl
Stream worker group:

- **Session logs** — file-monitor source watching `$CLAUDE_HOME` for `.jsonl`
  transcripts (assistant turns, user prompts, tool decisions, etc.)
- **OpenTelemetry** — OTLP/gRPC source on port 4317 (api_request, token_usage,
  cost metrics, error events, etc.)

Both pipelines tag events with Splunk-canonical fields:

| Pipeline | sourcetype | index | datatype |
|---|---|---|---|
| `claude-code-otel` | `claude:code:otel` | `claude-code` | `claude-code-otel` |
| `claude-code-session-logs` | `claude:code:session_logs` | `claude-code` | `claude-code-session-logs` |

## Pack-specific files (you may edit these freely)

- `package.json` — pack metadata
- `default/inputs.yml` — file-monitor + OTLP source config
- `default/pipelines/route.yml` — routes (filter on top-level `datatype`, set by the input's metadata)
- `default/pipelines/claude-code-{otel,session-logs}/conf.yml` — Eval functions setting sourcetype/index/datatype
- `default/samples.yml` — sample catalog
- `data/samples/*.json` — captured sample events
- `tests/fixtures/<pipeline>/sample.{json,expected.json}` — Vitest fixtures
- `README.md` — describe what this pack does

## Generic files (DO NOT modify here — push changes upstream to the template)

- `tests/cribl-client.ts`, `tests/parse-filter.ts`, `tests/global-setup.ts`,
  `tests/test-helpers.ts`, `tests/routes.test.ts`, `tests/pipelines.test.ts`
- `tests/package.json`, `tests/tsconfig.json`, `tests/vitest.config.ts`,
  `tests/pnpm-lock.yaml`
- `tests/generate-fixtures.ts` (re-run when fixtures need regeneration)
- `biome.jsonc`, `flake.nix`, `.envrc`, `Makefile`, `docker-compose.yml`,
  `.gitignore`
- `.github/workflows/{test,release,release-please}.yml`

If something here needs changing, open a PR against
[`dryvist/cc-edge-pack-template`](https://github.com/dryvist/cc-edge-pack-template)
and let it propagate.

## Workflow

```sh
direnv allow                  # activate nix-devenv typescript shell
cd tests && pnpm install      # install Vitest, biome, etc.
make docker-up                # start cribl/cribl test container
make test                     # vitest run (typecheck + 11 tests)
make docker-down              # stop test container
```

To regenerate expected fixtures (after pipeline changes):

```sh
make docker-up
cd tests
pnpm exec tsx generate-fixtures.ts <pipeline-name> fixtures/<pipeline>/sample.json
```

## Future work (not in scope right now)

- OpenTelemetry semantic conventions for generative AI (see
  <https://opentelemetry.io/docs/specs/semconv/gen-ai/>)
- Splunk Common Information Model (CIM) mappings on both pipelines
- PII masking for Claude Code session content (`message.content`,
  `toolUseResult.stdout`, etc.) before stream forwarding

These are deliberate next steps once the TS test harness has stabilized.

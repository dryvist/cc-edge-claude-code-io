# cc-edge-claude-code-io

Cribl Edge pack for collecting [Claude Code](https://claude.com/claude-code)
telemetry — session JSONL transcripts and OpenTelemetry metrics — and
forwarding it to a Cribl Stream worker group.

## Status

Initial scaffold. Currently ships only a demo passthrough pipeline inherited
from the [pack template](https://github.com/dryvist/cc-edge-pack-template).
Real pipelines (`claude-code-otel`, `claude-code-session-logs`) and matching
fixtures land in follow-up PRs.

## Installation

Install the pack into a Cribl Edge worker group via the Cribl UI:

1. Open Cribl Edge and navigate to **Packs**.
2. Click **Add Pack → Upload**.
3. Select a `.crbl` file from the
   [Releases](https://github.com/dryvist/cc-edge-claude-code-io/releases) page.
4. Confirm install and attach the pack to your worker group.

## Usage

Once installed, point your Claude Code clients at the pack's source:

- **Session logs** — file-monitor source watches `$CLAUDE_HOME` for `.jsonl`
  transcripts (assistant turns, user prompts, tool decisions).
- **OpenTelemetry** — OTLP/gRPC source on port 4317 (api_request, token_usage,
  cost metrics, error events).

The pack tags events with Splunk-canonical `sourcetype` / `index` / `datatype`
fields and forwards them upstream via the worker group's default destination.

## Local development

```sh
cd tests
pnpm install
pnpm run test       # vitest run (requires a Cribl container at localhost:9000)
```

See [`dryvist/cc-edge-pack-template/docs/development.md`](https://github.com/dryvist/cc-edge-pack-template/blob/main/docs/development.md)
for the full local-development workflow (Cribl container, fixture authoring,
release process).

## License

Apache-2.0 — see [`LICENSE`](LICENSE).

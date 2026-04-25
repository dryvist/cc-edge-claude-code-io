# CLAUDE.md — guidance for AI assistants working in this repo

This file is read by Claude Code (and other AI assistants supporting `CLAUDE.md`) on every session. It encodes the guardrails for working in this template — and, by inheritance, in any pack scaffolded from it.

## Repository Type

This is a **template repository** for new Cribl Edge / Stream packs. It is consumed via `gh repo create --template`. The files here become the starting point for every downstream pack.

## Generic vs Pack-Specific

The single most important rule: **distinguish generic files from pack-specific files.**

**Generic** (DO NOT modify in pack repos — only in this template):
- `tests/cribl_client.py`
- `tests/conftest.py`
- `tests/test_pipelines.py`
- `tests/test_routes.py`
- `tests/requirements.txt`
- `Makefile`
- `docker-compose.yml`
- `.github/workflows/test.yml` (only the `pack_type:` value changes per pack)
- `.github/workflows/release.yml`

If you find yourself wanting to modify any of the above in a pack repo, **stop**. Either:

1. The change belongs in this template (open a PR here, then propagate to packs), or
2. The change should be expressed as fixture data, not code.

**Pack-specific** (free to modify per-pack):
- `package.json` (name, version, displayName, tags, description)
- `default/pack.yml` (logo)
- `default/inputs.yml` (sources)
- `default/pipelines/route.yml` (routes)
- `default/pipelines/<name>/conf.yml` (pipeline functions)
- `default/samples.yml` (sample catalog)
- `data/samples/*.json` (sample events)
- `tests/fixtures/<pipeline>/*.json` (test fixtures)
- `README.md` (describe your specific pack)
- `LICENSE` (use Apache-2.0 unless instructed otherwise)

## Validator Rules (vct-cribl-pack-validator)

Always enforce these — they are non-negotiable per the [validator skill](https://github.com/VisiCore/vct-cribl-pack-validator):

| Rule | What it means |
|---|---|
| Pack ID format | `cc-edge-<source>-io` for Edge, `cc-stream-<source>-io` for Stream |
| No pipeline named `main` | All pipelines must have descriptive names |
| All routes use `output: __group` | Never `input_id` (breaks on source rename) |
| All sources have `metadata.datatype` | So route filters can match |
| Filters must be dynamic | Never literal `false` / `0` |
| No hardcoded paths | Use environment variables (`$MY_LOG_PATH`) |
| No hardcoded credentials | Use Cribl secrets |
| PII fields masked | `email`, `username`, `*_id`, `src_ip`, etc. before destinations |

## Fixture Convention

When adding tests, follow filesystem convention — no Python edits required:

```
tests/fixtures/<pipeline-name>/<case>.json           # input
tests/fixtures/<pipeline-name>/<case>.expected.json  # optional expected output (partial match)
```

The generic `test_pipelines.py` auto-discovers and parametrizes one test per `<case>.json` it finds. If `<case>.expected.json` is missing, the case is a smoke test (asserts non-empty output only). When you add an expected file, the assertions tighten automatically.

Prefer richer fixtures over richer Python. If the assertion can't be expressed as a partial-match expected event, it probably shouldn't be a test — consider whether it's really a pipeline behavior or something else.

## Don't Invent — Reuse

Per the user's rules:

- **Use existing Cribl tooling** — `cribl pipe`, the management API, official Docker images. Don't reinvent.
- **Use existing third-party Actions** — `softprops/action-gh-release`, `rlespinasse/github-slug-action`, `actions/setup-python`. Don't write custom packaging shell scripts.
- **Use the criblpacks pattern** — that's where `cribl_client.py` came from. When extending, mirror their idioms.
- **Use vct-cribl-pack-validator** — for deep structural validation, not custom-rolled YAML parsers.

## Workflow

For any pack work:

1. `/refresh-repo` then create a worktree for the change (per user's global CLAUDE.md).
2. Modify only pack-specific files (see lists above).
3. `make test` locally before committing.
4. `make validate` before tagging a release.
5. Tag `vX.Y.Z` to trigger the release workflow.

## When in Doubt

- Read [`VisiCore/cc-edge-claude-code-io`](https://github.com/VisiCore/cc-edge-claude-code-io) — the gold-standard reference pack.
- Read [`criblpacks/cribl-palo-alto-networks`](https://github.com/criblpacks/cribl-palo-alto-networks) — Cribl's own test pattern reference.
- Read [`VisiCore/vct-cribl-pack-validator`](https://github.com/VisiCore/vct-cribl-pack-validator) — the authoritative ruleset.
- Don't add scripts. If you're tempted to write a script, ask first whether a Cribl-native or GitHub Action equivalent already exists.

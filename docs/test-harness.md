# Test harness

Vitest-based, lives entirely in `tests/`. Auto-discovers fixtures by filesystem
convention — no TypeScript edits needed to add tests.

## What gets tested

| Suite | What it asserts |
|---|---|
| `routes.test.ts` (structure) | route.yml exists, every route has a pipeline, every referenced pipeline file exists, routes use `output: __group`, filters aren't statically falsy, no pipeline named `main` |
| `routes.test.ts` (dynamic flow) | Per route: a synthetic event matching its filter triggers the named pipeline and isn't dropped (uses live Cribl) |
| `pipelines.test.ts` | Per fixture: pipeline produces non-empty output; partial-match against `<case>.expected.json` if present; required-fields assertion (`sourcetype`+`index` for Edge; `host`+`source`+`_time` for Stream) unless `.skip-required-fields` marker present |

## Fixture convention

```
tests/fixtures/<pipeline-name>/<case>.json           # input event(s)
tests/fixtures/<pipeline-name>/<case>.expected.json  # optional partial-match expected output
tests/fixtures/.skip-required-fields                 # optional org-wide opt-out marker
```

The generic `pipelines.test.ts` auto-discovers and parametrizes one Vitest case
per `<case>.json`. Add a fixture → tests run automatically. Remove a fixture →
tests stop running. No code changes.

## Generating expected fixtures

Run input through the live Cribl container; capture the output trimmed to
partial-match keys (`sourcetype`, `index`, `datatype`, `_raw`, `_time`):

```sh
make docker-up
cd tests
pnpm exec tsx generate-fixtures.ts <pipeline-name> fixtures/<pipeline>/<case>.json
```

Writes `<case>.expected.json` next to the input.

## Required-fields assertion

Edge packs are expected to set `sourcetype` and `index` (typically via an Eval
function in the pipeline). Stream packs set `host`, `source`, `_time`. The
assertion fires unconditionally on every pipeline test unless you opt out by
creating an empty `tests/fixtures/.skip-required-fields` file (use this for
pass-through packs whose downstream sets these fields).

## CriblClient API surface

`tests/cribl-client.ts` wraps the Cribl management API. Reference:

| Method | Purpose |
|---|---|
| `waitUntilReady()` | Block until `/health` returns 200 |
| `installPack(tarball, expectedId?)` | Upload `.crbl` + poll until pack registers |
| `deletePack(packId)` | Remove pack |
| `saveSample(name, events)` / `deleteSample(id)` | Sample lifecycle |
| `runPipeline(pipeline, sampleId, {pack})` | Execute via `/preview` (mode `pipe`); returns output events |
| `runRouteFlow(sampleId, events, {pack})` | Local route-matcher fallback (Cribl has no `mode:route`); finds matching route in `route.yml`, then runs its pipeline |
| `assertRequiredFields(events, packType?)` | Assert canonical fields per pack type |
| `startCapture(filter, ...)` / `readCapture(id, ...)` | Live capture primitives (reserved for future integration tests) |
| `createPackTarball(packRoot)` (static) | Build `.crbl` from on-disk pack contents |

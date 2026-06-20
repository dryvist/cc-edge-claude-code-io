# cc-edge-claude-code-io

> **Status: work in progress — not production-ready.** This pack is a
> template-derived shell. Its routes and pipelines are demo placeholders today;
> the canonical Claude Code telemetry pipelines are still being authored. Don't
> deploy it as-is.

A [Cribl Edge](https://docs.cribl.io/edge/) pack that collects Claude Code
telemetry from OpenTelemetry (OTLP) and/or session-log sources, normalizes it,
and routes it for downstream delivery with Splunk-canonical fields
(`sourcetype`, `index`, `datatype`) stamped on every event.

The pack contains only declarative Cribl configuration (sources, routes,
pipelines, samples) plus a Python test harness that exercises those pipelines
against the Cribl management API. CI delegates to reusable GitHub Actions
workflows; tagging a release builds and uploads the `.crbl` artifact.

## Installation

Clone the repo and install the Python test dependencies into a repo-local
virtualenv:

```sh
git clone git@github.com:dryvist/cc-edge-claude-code-io.git
cd cc-edge-claude-code-io
make install   # creates .venv at repo root and installs test deps
```

Build the deployable pack artifact:

```sh
make build     # produces cc-edge-claude-code-io-<version>.crbl
```

Import the resulting `.crbl` into Cribl Stream or Cribl Edge via **Manage →
Packs → Add Pack → Import from File**.

## Usage

`make help` lists every target. The common loop:

| Target | What it does |
| --- | --- |
| `make install` | Create `.venv` and install Python test dependencies |
| `make build` | Build the `.crbl` pack artifact |
| `make docker-up` | Start a local `cribl/cribl` container on `localhost:9000` |
| `make test` | Run the pytest suite against the running container |
| `make docker-down` | Stop and remove the container |
| `make validate` | Build the `.crbl` and print validation instructions |
| `make clean` | Remove build artifacts, the venv, and the Docker container |

### Configure the pack

Pack configuration and metadata are edited directly:

1. **`package.json`** (at the root) — `name`, `description`, `displayName`,
   `tags`. The pack name follows the convention `cc-edge-<source>-io` (Edge) or
   `cc-stream-<source>-io` (Stream).
2. **`default/inputs.yml`** — source definitions. Every input must declare
   `metadata.datatype` so route filters can match it.
3. **`default/pipelines/route.yml`** — routes. Every route must set
   `output: __group` (never `input_id`, which breaks on source rename).
4. **`default/pipelines/<name>/conf.yml`** — pipeline functions. No pipeline may
   be named `main`.
5. **`default/samples.yml`** + **`data/samples/*.json`** — sample events for
   Cribl's UI sample-data preview.

### Add tests

Tests are driven by filesystem convention — no Python edits required:

```text
tests/fixtures/<pipeline-name>/<case>.json           # input event
tests/fixtures/<pipeline-name>/<case>.expected.json  # optional expected output
```

The test harness auto-discovers and parametrizes one test per `<case>.json`. A
case with no `<case>.expected.json` is a smoke test (asserts non-empty output);
adding the expected file tightens the assertions automatically. See
[`tests/README.md`](tests/README.md) for details.

### Run a release

Tag `vX.Y.Z` and push the tag. The release workflow builds the `.crbl` and
uploads it to a GitHub release.

## Layout

```text
.
├── .github/workflows/
│   ├── release.yml          # Build + publish the .crbl on tag
│   └── test.yml             # Run the test harness on push / PR
├── data/
│   └── samples/             # Cribl sample events (referenced by samples.yml)
├── default/
│   ├── inputs.yml           # Source definitions
│   ├── pack.yml             # Branding (logo)
│   ├── pipelines/
│   │   ├── route.yml        # Routes
│   │   └── <name>/conf.yml  # Pipeline functions
│   └── samples.yml          # Sample catalog
├── tests/
│   ├── conftest.py          # Pytest fixtures / Cribl client wiring
│   ├── cribl_client.py      # Cribl management API client
│   ├── test_pipelines.py    # Pipeline fixtures → expected output
│   ├── test_routes.py       # Route-config assertions
│   ├── requirements.txt     # Python test dependencies
│   ├── fixtures/            # Per-pipeline fixture data
│   └── README.md
├── docker-compose.yml       # Local cribl/cribl container for tests
├── Makefile                 # Build / test / validate entry points
├── package.json             # Pack manifest (name, version, tags)
└── LICENSE                  # Apache-2.0
```

## API

This pack exposes no programmatic API. Its interfaces are:

- **CLI surface (Makefile):** `make help`, `install`, `build`, `docker-up`,
  `docker-down`, `test`, `validate`, `clean`.
- **Test fixture surface:** the filesystem convention under
  `tests/fixtures/<pipeline>/<case>.{json,expected.json}` — see
  [`tests/README.md`](tests/README.md).
- **CI surface:** `.github/workflows/test.yml` and `release.yml`, which delegate
  to reusable workflows.
- **Output contract:** events emitted with Splunk-canonical fields
  (`sourcetype`, `index`, `datatype`) for downstream Cribl / Splunk delivery.

## References

- [Cribl Edge docs](https://docs.cribl.io/edge/)
- [Cribl Packs docs](https://docs.cribl.io/stream/packs/)
- [Cribl management API](https://docs.cribl.io/api-reference/)

## License

Apache-2.0 — see [`LICENSE`](LICENSE).

---

> Part of a [larger ecosystem of ~40 repos](https://docs.jacobpevans.com) — see how it all fits together.

# cc-edge-pack-template

Template repository for new Cribl Edge / Stream packs. Provides the full DRY scaffolding (test harness, validation, release packaging, Makefile, Docker setup) so per-pack repos only contain pack-specific configuration and fixture data.

This template is built around two existing references:

- **Layout & convention**: based on [`VisiCore/cc-edge-claude-code-io`](https://github.com/VisiCore/cc-edge-claude-code-io), the gold-standard pack deployed to the Cribl dispensary.
- **Test pattern**: adopts the [criblpacks](https://github.com/criblpacks) approach (Python + Docker + Cribl management API). See [`criblpacks/cribl-palo-alto-networks/test/`](https://github.com/criblpacks/cribl-palo-alto-networks/tree/main/test).

CI delegates entirely to reusable workflows in [`dryvist/.github`](https://github.com/dryvist/.github).

## Installation

Create a new pack repo from this template:

```sh
gh repo create my-org/cc-edge-mything-io \
  --template dryvist/cc-edge-pack-template \
  --public \
  --clone

cd cc-edge-mything-io
make install   # creates .venv at repo root and installs deps
```

If you prefer the GitHub UI: navigate to this repo, click **Use this template** → **Create a new repository**.

## Usage

After scaffolding from the template:

1. **Customize `package.json`**: replace `name`, `description`, `displayName`, `tags`. Pack name MUST follow the validator convention `cc-edge-<source>-io` (or `cc-stream-<source>-io`).
2. **Set the pack type in `.github/workflows/test.yml`**: change `pack_type: edge` to `stream` if this is a Stream pack.
3. **Define your inputs** in `default/inputs.yml`. Every input must declare `metadata.datatype` so route filters can match.
4. **Define your routes** in `default/pipelines/route.yml`. Replace the `REPLACE_*` placeholders. All routes MUST `output: __group` (validator rule).
5. **Define your pipelines** in `default/pipelines/<name>/conf.yml`. No pipeline named `main` (validator rule).
6. **Drop sample events** in `data/samples/*.json` and catalog them in `default/samples.yml`.
7. **Author test fixtures** in `tests/fixtures/<pipeline-name>/`:
   - `<case>.json` (input)
   - `<case>.expected.json` (optional partial-match expected output)
8. **Run locally**: `make docker-up && make test`
9. **Validate**: `make validate` builds the `.crbl` and prints the command to run [`/validate-pack`](https://github.com/VisiCore/vct-cribl-pack-validator) against it.
10. **Push & release**: tag `vX.Y.Z` and the release workflow builds and uploads the `.crbl` to a GitHub release.

## Layout

```
.
├── .github/workflows/
│   ├── release.yml          # Calls dryvist reusable workflow
│   └── test.yml             # Calls dryvist reusable workflow
├── data/
│   └── samples/             # Cribl sample events (referenced by samples.yml)
├── default/
│   ├── inputs.yml           # Source definitions — pack-specific
│   ├── pack.yml             # Branding (logo) — pack-specific
│   ├── pipelines/
│   │   ├── route.yml        # Routes — pack-specific
│   │   └── <name>/conf.yml  # Pipeline functions — pack-specific
│   └── samples.yml          # Sample catalog — pack-specific
├── tests/
│   ├── conftest.py          # GENERIC — never modify
│   ├── cribl_client.py      # GENERIC — never modify
│   ├── test_pipelines.py    # GENERIC — never modify
│   ├── test_routes.py       # GENERIC — never modify
│   ├── requirements.txt     # GENERIC — bump versions in template, propagate
│   ├── fixtures/            # Per-pack fixture data
│   │   └── <pipeline>/
│   │       ├── <case>.json              # input
│   │       └── <case>.expected.json     # expected (optional)
│   └── README.md
├── docker-compose.yml       # GENERIC — never modify
├── Makefile                 # GENERIC — never modify
├── package.json             # PACK-SPECIFIC — name, version, tags
├── README.md                # PACK-SPECIFIC — describe your pack
├── LICENSE                  # GENERIC — Apache-2.0
└── CLAUDE.md                # GENERIC — AI assistant guidance
```

The "GENERIC" files are propagated from this template. When the template improves, downstream packs should pull the changes via cherry-pick or by re-running the relevant section. When something is pack-specific, edit it freely in the pack repo.

## API

This template doesn't expose a programmatic API. It provides:

- **CLI surface (Makefile)**: `make help`, `install`, `build`, `docker-up`, `docker-down`, `test`, `validate`, `clean`
- **Test fixture surface**: filesystem convention under `tests/fixtures/<pipeline>/<case>.{json,expected.json}` — see `tests/README.md` for details
- **CI surface**: `.github/workflows/test.yml` and `release.yml` — both delegate to `dryvist/.github` reusable workflows

## Contributing

This template is the source of truth for shared pack infrastructure across the Cribl pack ecosystem. Changes here propagate to every downstream pack.

When updating:

1. Make changes in this repo on a feature branch.
2. Open a PR against `main`. Note that the template's own CI workflows are gated on `is_template == false`, so they won't run here — verify against a real pack instead.
3. Pick a downstream pack (e.g. `VisiCore/cc-edge-claude-code-io`) and apply the same changes there in a parallel PR. Confirm CI green.
4. Merge both. Document the propagation expectation in the PR description.

## License

Apache-2.0 — see `LICENSE`.

## References

- [VisiCore/cc-edge-claude-code-io](https://github.com/VisiCore/cc-edge-claude-code-io) — pilot pack and structural reference
- [VisiCore/vct-cribl-pack-validator](https://github.com/VisiCore/vct-cribl-pack-validator) — Claude Code skill running 27+ structural checks
- [criblpacks](https://github.com/criblpacks) — Cribl's official pack org; we adopt their test pattern
- [dryvist/.github](https://github.com/dryvist/.github) — hosts the reusable workflows this template calls
- [Cribl management API](https://docs.cribl.io/api-reference/)
- [Cribl pack docs](https://docs.cribl.io/stream/packs/)

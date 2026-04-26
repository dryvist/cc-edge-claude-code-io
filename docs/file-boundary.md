# Generic vs pack-specific files

The single most important rule for working in any pack scaffolded from this
template: **distinguish generic files from pack-specific files.**

## Generic — DO NOT modify in pack repos

Edit only here in the template; updates propagate when packs sync.

- `tests/cribl-client.ts`, `tests/parse-filter.ts`, `tests/global-setup.ts`,
  `tests/test-helpers.ts`, `tests/routes.test.ts`, `tests/pipelines.test.ts`,
  `tests/generate-fixtures.ts`
- `tests/package.json`, `tests/tsconfig.json`, `tests/vitest.config.ts`,
  `tests/pnpm-lock.yaml`
- `scripts/build-crbl.sh`, `scripts/validate-pack-structure.sh`
- `biome.jsonc`, `.editorconfig`, `lefthook.yml`, `.yamllint.yml`
- `Makefile`, `docker-compose.yml`
- `.github/workflows/cribl-pack-test.yml` (reusable)
- `.github/workflows/cribl-pack-release.yml` (reusable)
- `.github/workflows/test.yml` (caller — only `pack_type:` value changes per pack)
- `.github/workflows/release.yml`, `.github/workflows/release-please.yml`

If you find yourself wanting to modify any of the above in a pack repo, **stop**.
Either:

1. The change belongs in this template (open a PR here, then propagate to packs), or
2. The change should be expressed as fixture data (`tests/fixtures/<pipeline>/`).

## Pack-specific — free to modify per-pack

- `package.json` (name, version, displayName, tags, description)
- `default/pack.yml`, `default/inputs.yml`, `default/samples.yml`
- `default/pipelines/route.yml`
- `default/pipelines/<name>/conf.yml` (Eval, Drop, etc.)
- `data/samples/*.json`
- `tests/fixtures/<pipeline>/*.json`
- `tests/fixtures/.skip-required-fields` (optional opt-out marker)
- `.release-please-manifest.json`, `release-please-config.json`
- `README.md`, `LICENSE`

# `.github/` — workflows for this template

Reusable GitHub Actions workflows callable from any dryvist Cribl pack via
`uses: dryvist/cc-edge-pack-template/.github/workflows/<file>@main`. Caller
workflows in this repo (`test.yml`, `release.yml`, `release-please.yml`) wire
them up to GitHub events.

## Installation

These workflows install themselves implicitly when a new pack scaffolds from
`dryvist/cc-edge-pack-template` (`gh repo create --template`). The caller
workflows under `.github/workflows/` are copied verbatim; the reusable
workflows they reference resolve at runtime against
`dryvist/cc-edge-pack-template@main`.

If you're adding a workflow to a non-template repo manually, copy the relevant
caller from this directory into your repo's `.github/workflows/` and adjust
the `uses:` ref if you want to pin a specific template version (default
`@main` follows the template's main branch).

## Usage

Once installed, the workflows trigger automatically:

- Open a PR touching `default/`, `data/samples/`, `tests/`, or `package.json`
  → `test.yml` runs validate + Vitest.
- Push to `main` → `release-please.yml` opens or updates the release PR.
- Merge a release PR → release-please tags the version, which triggers
  `release.yml` → builds the `.crbl` and publishes to GitHub Releases.

No manual invocation is needed. Override defaults by editing the caller
workflow's `with:` block (e.g., bump `cribl_version` to test a specific
upstream Cribl release).

## Reusable workflows

### `cribl-pack-test.yml`

Validates pack structure + runs the TypeScript Vitest suite against a
`cribl/cribl` service container.

| Input | Required | Default | Purpose |
|---|---|---|---|
| `pack_type` | yes | — | `edge` or `stream` (drives validator naming convention + required-fields assertion) |
| `cribl_version` | no | `latest` | `cribl/cribl` Docker tag |
| `node_version` | no | `lts/*` | Node.js version |
| `yq_version` | no | `4.44.5` | Pinned `mikefarah/yq` version |

Jobs:

1. **validate** — installs `yq` (pinned via `dcarbone/install-yq-action`),
   lints YAML (`frenck/action-yamllint`, config from `.yamllint.yml`), runs
   `scripts/validate-pack-structure.sh`.
2. **test** — sets up Node + pnpm (cached), installs deps, runs Biome lint,
   typechecks, waits for Cribl health endpoint
   (`iFaxity/wait-on-action`), runs `pnpm run test`.

### `cribl-pack-release.yml`

Builds a `.crbl` tarball via `scripts/build-crbl.sh` and publishes it to
GitHub Releases (`softprops/action-gh-release`).

| Input | Required | Default | Purpose |
|---|---|---|---|
| `additional_files` | no | `''` | Space-separated extra files to include in tarball; `LICENSE` auto-included if present |

Triggered by tag push in the calling workflow (typically by release-please
when a release PR merges).

## Caller workflows in this repo

| File | Trigger | Calls |
|---|---|---|
| `workflows/test.yml` | PR + push to main (paths-filtered) | `cribl-pack-test.yml` (this repo) |
| `workflows/release.yml` | tag push matching `v*` | `cribl-pack-release.yml` (this repo) |
| `workflows/release-please.yml` | push to main | `_release-please.yml` (inherited from `JacobPEvans/.github`) |

## Updating reusable workflow inputs

Adding/renaming an input is a breaking change for every consumer pack. Use the
`workflow_call.inputs.<name>.default` field to keep the change backward
compatible whenever possible. Bump major version of the workflow only if you
absolutely cannot.

## Pinning external actions

Per [`SECURITY.md`](https://github.com/dryvist/.github/blob/main/SECURITY.md):

- Trusted (`actions/*`, `pnpm/action-setup`, `softprops/action-gh-release`):
  semver tag pins (`@v4`, etc.)
- Untrusted (everything else): SHA pins. Renovate (per the org's
  `renovate.json`) auto-converts version tags to SHA on first run.

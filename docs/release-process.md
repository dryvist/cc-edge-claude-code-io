# Release process

Releases are automated via [release-please](https://github.com/googleapis/release-please).

## How it works

1. Merge PRs to `main` using conventional commits (`fix:`, `feat:`, `chore:`, etc.).
2. release-please opens a release PR (or updates an existing one) with the
   computed version bump + changelog.
3. Review the release PR. When ready, merge it.
4. The release workflow tags the new version and publishes the `.crbl` artifact
   to GitHub Releases.

## Conventional commit → version bump

| Commit prefix | Bump |
|---|---|
| `fix:` | patch (`1.2.3` → `1.2.4`) |
| `feat:` | minor (`1.2.3` → `1.3.0`) |
| `BREAKING CHANGE:` footer | **blocked** — see below |

## Major bumps require manual intervention

The org-wide release-please workflow forbids automated major bumps (any
`BREAKING CHANGE:` footer would normally trigger one). If you need a major:

1. Edit `.release-please-manifest.json` directly to bump the major version.
2. Commit + open a PR.
3. release-please picks up the manifest change and proceeds normally.

This is intentional friction — major bumps should be a human decision, not a
side effect of a stray footer.

## Don't tag manually

The release workflow runs only when release-please's bot tags a release. Don't
push tags manually — they'll bypass the changelog automation and produce
inconsistent state.

## Release artifacts

Each release publishes:

- `<pack-name>-<version>.crbl` — versioned tarball
- `<pack-name>.crbl` — "latest" alias (overwritten each release)

Built by `scripts/build-crbl.sh`, which the reusable release workflow invokes.

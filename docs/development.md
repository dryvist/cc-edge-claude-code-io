# Local development

## Requirements

- Node.js 20+ (LTS recommended)
- pnpm 10+
- Docker (for the local Cribl test container)

Install Node + pnpm via your package manager of choice. Common paths:

```sh
# macOS via Homebrew
brew install node pnpm

# Linux via npm
curl -fsSL https://get.pnpm.io/install.sh | sh -

# Or via Corepack (ships with Node 16+)
corepack enable pnpm
```

## First-time setup

```sh
git clone https://github.com/dryvist/cc-edge-<pack>-io.git
cd cc-edge-<pack>-io
make install            # pnpm install in tests/ (also installs lefthook git hooks)
```

`make install` runs the `prepare` script in `tests/package.json`, which
installs lefthook git hooks at the repo root. Pre-commit Biome auto-format
fires on every `git commit` going forward.

## Iterating

```sh
make docker-up          # start cribl/cribl test container
make test               # vitest run (typecheck + 11 baseline tests)
make lint               # biome check
make format             # biome format --write
make typecheck          # tsc --noEmit
make docker-down        # stop cribl
make clean              # purge node_modules, .crbl artifacts, container state
```

## Skipping the pre-commit hook

```sh
LEFTHOOK=0 git commit -m "..."
```

Use sparingly — CI runs the same checks and will catch what you skipped.

## Optional: Nix devShell

If you use Nix, the org's typescript devShell pins the toolchain (Node, pnpm,
TypeScript, Biome) so it's identical across machines:

```sh
nix develop github:JacobPEvans/nix-devenv?dir=shells/typescript
```

Or via direnv:

```sh
direnv allow            # uses flake.nix at the repo root
```

This is purely optional — the standard `brew`/`apt`/`corepack` install path
above works equally well.

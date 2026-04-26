# Validator rules (vct-cribl-pack-validator)

Non-negotiable rules per the [validator skill](https://github.com/VisiCore/vct-cribl-pack-validator).
The CI `validate` job and `scripts/validate-pack-structure.sh` enforce the
machine-checkable subset; the rest are conventions to follow.

| Rule | What it means | Enforced by |
|---|---|---|
| Pack ID format | `cc-edge-<source>-io` for Edge, `cc-stream-<source>-io` for Stream | CI (warning) |
| No pipeline named `main` | All pipelines must have descriptive names | `routes.test.ts` |
| All routes use `output: __group` | Never `input_id` (breaks on source rename) | `routes.test.ts` + CI (warning) |
| All sources have `metadata.datatype` | So route filters can match | Convention; verify locally |
| Filters must be dynamic | Never literal `false` / `0` | `routes.test.ts` |
| No hardcoded paths | Use environment variables (`$MY_LOG_PATH`) | Code review |
| No hardcoded credentials | Use Cribl secrets | Code review |
| PII fields masked | `email`, `username`, `*_id`, `src_ip`, etc. before destinations | Code review |

## Running the deep validator locally

```sh
make build      # produces <pack-name>-<version>.crbl
# Then from the validator repo:
cd ~/git/vct-cribl-pack-validator/main
claude /validate-pack /path/to/<pack-name>-<version>.crbl
```

`make validate` prints the exact command after building.

# Contributing

Thank you for your interest in contributing to **mts-client-integration-mcp**.

## Development setup

1. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/sportradar/mts-client-integration-mcp.git
   cd mts-client-integration-mcp
   uv sync
   ```

   **Corporate PyPI mirror:** if direct PyPI is blocked, copy `.envrc.example` to
   `.envrc`, point `UV_DEFAULT_INDEX` at your mirror (see comment in the example file),
   run `direnv allow`, and keep `.envrc` out of git.

   The committed `uv.lock` uses **public PyPI** URLs. Do not run `uv lock` through the
   corporate proxy and commit the result. Regenerate the lock on GitHub Actions, VPN, or
   any host with `https://pypi.org` access:

   ```bash
   uv lock --default-index https://pypi.org/simple
   ```

2. Optional: install pre-commit hooks:

   ```bash
   uv run pre-commit install
   ```

## Before opening a pull request

Run these checks from the repository root:

```bash
uv run ruff check src scripts
uv run ruff format --check src scripts
uv run mypy
uv run pytest --cov
```

Fix any failures in the same PR. CI (`.github/workflows/ci.yml`) runs the same checks on
every pull request; `pytest --cov` fails when branch coverage drops below the
`fail_under` threshold in `pyproject.toml`. Raise that threshold when you add coverage.

Shared test data builders live in `src/tests/factories.py` and shared fixtures in
`src/tests/conftest.py`. Prefer `pytest.mark.parametrize` (with readable `id=`s) over
loops or copy-pasted tests when cases differ only in data.

### Mutation testing

`mutmut` checks that tests actually catch behaviour changes in the business-rule and
ACK state-machine modules (scope: `[tool.mutmut]` in `pyproject.toml`). The CI
`Mutation testing` job runs it on every pull request and fails when the mutation score
drops below `[tool.mutation-gate] fail_under`. Raise that threshold when you kill
surviving mutants.

Run it on Linux (CI or a container). On macOS, mutants that fork after the simulator
tests start threads crash, so local scores are unreliable and the gate refuses them.

```bash
uv run mutmut run
uv run mutmut export-cicd-stats
uv run python scripts/check_mutation_score.py   # same gate as CI
uv run mutmut results                           # list surviving mutants
uv run mutmut show <mutant>                     # diff for one survivor
```

A surviving mutant means a code change went unnoticed by the suite; add or tighten an
assertion rather than excluding it.

## Pull requests

1. Open an issue or comment on an existing one so maintainers can align on the change.
2. Keep PRs focused; avoid unrelated refactors.
3. Update README or tool docstrings when behavior or MCP contracts change.
4. Add or extend tests when you change validation, builders, or simulator behavior.

## Contributor License Agreement

External contributions may require signing a Contributor License Agreement (CLA)
before merge. Maintainers will let you know when that applies.

## Code of conduct

This project follows the [Code of Conduct](CODE_OF_CONDUCT.md). Participate accordingly.

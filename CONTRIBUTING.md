# Contributing

Thank you for your interest in contributing to **mts-client-integration-mcp**.

## Development setup

1. Clone the repository and install dependencies:

   ```bash
   git clone https://github.com/sportradar/mts-client-integration-mcp.git
   cd mts-client-integration-mcp
   uv sync
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
uv run pytest
```

Fix any failures in the same PR.

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

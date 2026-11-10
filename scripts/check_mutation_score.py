#!/usr/bin/env -S uv run
"""Fail when the mutmut mutation score drops below ``[tool.mutation-gate] fail_under``.

Run after ``mutmut run`` and ``mutmut export-cicd-stats``. Score is the share of
mutants the suite detected: (killed + timeout) / (killed + timeout + survived + no_tests).
"""

from __future__ import annotations

import json
import os
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
STATS_FILE = PROJECT_ROOT / "mutants/mutmut-cicd-stats.json"
PYPROJECT = PROJECT_ROOT / "pyproject.toml"


@dataclass(frozen=True)
class MutationStats:
    killed: int
    timeout: int
    survived: int
    no_tests: int
    segfault: int

    @property
    def detected(self) -> int:
        return self.killed + self.timeout

    @property
    def scored(self) -> int:
        return self.detected + self.survived + self.no_tests

    @property
    def score(self) -> float:
        return 100.0 * self.detected / self.scored if self.scored else 0.0


def load_stats(path: Path) -> MutationStats:
    if not path.exists():
        msg = f"{path} not found; run `mutmut run` then `mutmut export-cicd-stats` first."
        raise FileNotFoundError(msg)
    raw = json.loads(path.read_text(encoding="utf-8"))
    return MutationStats(
        killed=int(raw["killed"]),
        timeout=int(raw["timeout"]),
        survived=int(raw["survived"]),
        no_tests=int(raw["no_tests"]),
        segfault=int(raw["segfault"]),
    )


def load_threshold(path: Path) -> float:
    config = tomllib.loads(path.read_text(encoding="utf-8"))
    return float(config["tool"]["mutation-gate"]["fail_under"])


def main() -> int:
    stats = load_stats(STATS_FILE)
    threshold = load_threshold(PYPROJECT)
    report = (
        f"Mutation score: {stats.score:.2f}% "
        f"({stats.detected} detected / {stats.scored} scored, {stats.survived} survived, "
        f"{stats.no_tests} without tests); required: {threshold:.2f}%"
    )
    print(report)
    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as fh:
            fh.write(f"## Mutation testing\n\n{report}\n\n")

    if stats.segfault:
        print(
            f"{stats.segfault} mutants crashed the test process; the score is unreliable. "
            "This happens on macOS (fork after threads); run on Linux.",
            file=sys.stderr,
        )
        return 1
    if stats.score < threshold:
        print(
            "Mutation score below threshold: run `uv run mutmut results` and add or tighten "
            "assertions for the surviving mutants.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

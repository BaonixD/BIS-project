"""Run Ruff checks without modifying files.

Usage: ``uv run python scripts/lint.py``. Fix explicitly with
``uv run ruff check --fix .`` and ``uv run ruff format .``.
"""

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

CHECKS: tuple[tuple[str, ...], ...] = (
    ("ruff", "check", "."),
    ("ruff", "format", "--check", "."),
)


def main() -> int:
    exit_code = 0
    for check in CHECKS:
        print(f"$ {' '.join(check)}", flush=True)
        result = subprocess.run([sys.executable, "-m", *check], cwd=PROJECT_ROOT, check=False)
        exit_code = exit_code or result.returncode
    return exit_code


if __name__ == "__main__":
    sys.exit(main())

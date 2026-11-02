"""The demo seed is a separate command: the application never imports it."""

import os
import subprocess
import sys
from pathlib import Path

CHECK = (
    "import sys\n"
    "from taxi_service.main import create_app\n"
    "create_app()\n"
    "print(sorted(name for name in sys.modules if name.startswith('taxi_service.seeds')))\n"
)


def test_creating_the_application_does_not_import_the_seed(tmp_path: Path) -> None:
    env = os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{tmp_path / 'unused-test.db'}"}

    result = subprocess.run(
        [sys.executable, "-c", CHECK],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"

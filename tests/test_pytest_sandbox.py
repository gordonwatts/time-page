from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner


def test_tmp_path_uses_repo_local_scratch(
    tmp_path: Path, sandbox_temp_root: Path
) -> None:
    assert tmp_path.parent.parent == sandbox_temp_root
    assert Path(tempfile.gettempdir()) == sandbox_temp_root


def test_cli_runner_isolated_filesystem_uses_repo_local_scratch(
    sandbox_temp_root: Path,
) -> None:
    runner = CliRunner()

    with runner.isolated_filesystem() as workspace:
        assert Path(workspace).parent.parent == sandbox_temp_root

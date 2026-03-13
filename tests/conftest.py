from __future__ import annotations

import contextlib
import itertools
import os
import re
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRATCH_PARENT = REPO_ROOT / "test-scratch"
SCRATCH_ROOT = SCRATCH_PARENT / "pytest-runtime"
_COUNTER = itertools.count()
_ORIGINAL_ENV = {name: os.environ.get(name) for name in ("TEMP", "TMP", "TMPDIR")}
_ORIGINAL_ISOLATED_FILESYSTEM = CliRunner.isolated_filesystem


def _sanitize_segment(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")
    return cleaned or "tmp"


def _remove_tree(path: Path) -> None:
    if not path.exists():
        return
    shutil.rmtree(path)
    if path.exists():
        raise RuntimeError(f"Failed to remove test scratch path: {path}")


def _remove_empty_parent(path: Path) -> None:
    if not path.exists():
        return
    try:
        next(path.iterdir())
    except StopIteration:
        path.rmdir()


def _allocate_dir(base: Path, label: str) -> Path:
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{next(_COUNTER):04d}-{_sanitize_segment(label)}"
    target.mkdir()
    return target


def _set_temp_environment(root: Path) -> None:
    temp_root = str(root)
    for name in ("TEMP", "TMP", "TMPDIR"):
        os.environ[name] = temp_root
    tempfile.tempdir = temp_root


def _restore_temp_environment() -> None:
    for name, value in _ORIGINAL_ENV.items():
        if value is None:
            os.environ.pop(name, None)
        else:
            os.environ[name] = value
    tempfile.tempdir = None


def _patch_isolated_filesystem() -> None:
    @contextlib.contextmanager
    def isolated_filesystem(
        self: CliRunner,
        temp_dir: str | os.PathLike[str] | None = None,
    ) -> Iterator[str]:
        cwd = Path.cwd()
        base = Path(temp_dir) if temp_dir is not None else SCRATCH_ROOT / "cli"
        workspace = _allocate_dir(base, "isolated-filesystem")
        try:
            os.chdir(workspace)
            yield str(workspace)
        finally:
            os.chdir(cwd)

    CliRunner.isolated_filesystem = isolated_filesystem


def _restore_isolated_filesystem() -> None:
    CliRunner.isolated_filesystem = _ORIGINAL_ISOLATED_FILESYSTEM


def pytest_sessionstart(session: pytest.Session) -> None:
    _remove_tree(SCRATCH_ROOT)
    _remove_empty_parent(SCRATCH_PARENT)
    SCRATCH_ROOT.mkdir(parents=True, exist_ok=True)
    _set_temp_environment(SCRATCH_ROOT)
    _patch_isolated_filesystem()


def pytest_sessionfinish(
    session: pytest.Session, exitstatus: int | pytest.ExitCode
) -> None:
    errors: list[str] = []

    try:
        _restore_isolated_filesystem()
    except Exception as exc:  # pragma: no cover - defensive teardown
        errors.append(f"failed to restore CliRunner.isolated_filesystem: {exc}")

    try:
        _restore_temp_environment()
    except Exception as exc:  # pragma: no cover - defensive teardown
        errors.append(f"failed to restore temp environment: {exc}")

    try:
        _remove_tree(SCRATCH_ROOT)
        _remove_empty_parent(SCRATCH_PARENT)
    except Exception as exc:
        errors.append(f"failed to clean scratch root {SCRATCH_ROOT}: {exc}")

    if errors:
        terminal_reporter = session.config.pluginmanager.get_plugin("terminalreporter")
        if terminal_reporter is not None:
            terminal_reporter.write_sep(
                "!", "sandbox temp cleanup failed", red=True, bold=True
            )
            for message in errors:
                terminal_reporter.write_line(message, red=True)
        session.exitstatus = pytest.ExitCode.INTERNAL_ERROR


@pytest.fixture(scope="session")
def sandbox_temp_root() -> Path:
    return SCRATCH_ROOT


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest, sandbox_temp_root: Path) -> Path:
    return _allocate_dir(sandbox_temp_root / "tmp-path", request.node.name)

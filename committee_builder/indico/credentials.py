"""Helpers for per-base-URL Indico API key storage and lookup."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from urllib.parse import urlparse

ENV_FILE_NAME = ".env"
API_KEY_PREFIX = "INDICO_API_KEY_"
ENV_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")


def normalize_base_url(base_url: str) -> str:
    """Normalize an Indico base URL to scheme://host[/prefix] without trailing slash."""
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f"Invalid base URL '{base_url}'. Include scheme and host.")

    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def api_key_env_name(base_url: str) -> str:
    """Return the deterministic env var name for a base URL."""
    normalized = normalize_base_url(base_url)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16].upper()
    return f"{API_KEY_PREFIX}{digest}"


def dotenv_path(cwd: Path | None = None) -> Path:
    """Return the local project-scoped .env path."""
    base_dir = cwd if cwd is not None else Path.cwd()
    return base_dir / ENV_FILE_NAME


def store_api_key(base_url: str, key: str, cwd: Path | None = None) -> Path:
    """Create or update the local .env file with the API key for a base URL."""
    env_path = dotenv_path(cwd)
    env_name = api_key_env_name(base_url)
    lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updated_lines: list[str] = []
    replaced = False
    for line in lines:
        match = ENV_LINE_RE.match(line)
        if match and match.group(1) == env_name:
            updated_lines.append(f"{env_name}={key}")
            replaced = True
            continue
        updated_lines.append(line)

    if not replaced:
        if updated_lines and updated_lines[-1] != "":
            updated_lines.append("")
        updated_lines.append(f"{env_name}={key}")

    env_path.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")
    return env_path


def load_dotenv_values(cwd: Path | None = None) -> dict[str, str]:
    """Load simple KEY=value pairs from the local .env file."""
    env_path = dotenv_path(cwd)
    if not env_path.exists():
        return {}

    values: dict[str, str] = {}
    for line in env_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = ENV_LINE_RE.match(line)
        if not match:
            continue
        name, value = match.groups()
        values[name] = _strip_quotes(value.strip())
    return values


def resolve_stored_api_key(base_url: str) -> str | None:
    """Resolve a project-local stored credential for a base URL."""
    dotenv_values = load_dotenv_values()
    return dotenv_values.get(api_key_env_name(base_url))


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value

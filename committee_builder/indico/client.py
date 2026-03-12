"""Thin Indico client integration layer."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from committee_builder.indico.config import IndicoSource


@dataclass(frozen=True)
class IndicoMeeting:
    """Normalized meeting record fetched from Indico."""

    remote_id: str
    title: str
    start_datetime: datetime
    description: str
    url: str | None


def fetch_meetings(
    source: IndicoSource,
    start_date: date,
    end_date: date,
    api_key_env: str = "INDICO_API_KEY",
    api_token_env: str = "INDICO_API_TOKEN",
) -> list[IndicoMeeting]:
    """Fetch meetings for a source and normalize payloads."""
    client = _build_client(
        base_url=source.base_url,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    raw_records = _query_records(client, source.category_id, start_date, end_date)
    return [_normalize_record(record) for record in raw_records]


def fetch_category_title(
    base_url: str,
    category_id: int,
    api_key_env: str = "INDICO_API_KEY",
    api_token_env: str = "INDICO_API_TOKEN",
) -> str:
    """Resolve a category title from Indico."""
    client = _build_client(
        base_url=base_url,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    raw_category = _query_category(client, category_id)
    category_title = str(_pick(raw_category, "title", "name", default="")).strip()
    if not category_title:
        raise RuntimeError(f"No title returned for category {category_id}.")
    return category_title


def _build_client(base_url: str, api_key_env: str, api_token_env: str) -> Any:
    api_key = os.getenv(api_key_env)
    api_token = os.getenv(api_token_env)
    if not api_key or not api_token:
        raise ValueError(
            f"Missing Indico credentials in env vars: {api_key_env}, {api_token_env}"
        )

    try:
        from indico_client.client import IndicoClient  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - tested via CLI behavior
        raise RuntimeError(
            "indico-client is required for meeting generation. Install it to use this command."
        ) from exc

    return IndicoClient(base_url=base_url, api_key=api_key, api_token=api_token)


def _query_records(
    client: Any, category_id: int, start_date: date, end_date: date
) -> list[Any]:
    """Attempt known query entry points supported by different client versions."""
    if hasattr(client, "list_events") and callable(client.list_events):
        return list(
            _try_call(
                client.list_events,
                attempts=[
                    {
                        "category_id": category_id,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    {"category": category_id, "start_date": start_date, "end_date": end_date},
                ],
            )
        )

    if (
        hasattr(client, "events")
        and hasattr(client.events, "list")
        and callable(client.events.list)
    ):
        return list(
            _try_call(
                client.events.list,
                attempts=[
                    {
                        "category_id": category_id,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                    {"category": category_id, "start_date": start_date, "end_date": end_date},
                ],
            )
        )

    raise RuntimeError("Unsupported indico-client API shape for fetching events.")


def _query_category(client: Any, category_id: int) -> Any:
    if hasattr(client, "get_category") and callable(client.get_category):
        return _try_call(
            client.get_category,
            attempts=[
                {"category_id": category_id},
                {"id": category_id},
                (category_id,),
            ],
        )

    if (
        hasattr(client, "categories")
        and hasattr(client.categories, "get")
        and callable(client.categories.get)
    ):
        return _try_call(
            client.categories.get,
            attempts=[
                {"category_id": category_id},
                {"id": category_id},
                (category_id,),
            ],
        )

    raise RuntimeError("Unsupported indico-client API shape for fetching categories.")


def _try_call(function: Any, attempts: list[Any]) -> Any:
    last_type_error: TypeError | None = None
    for attempt in attempts:
        try:
            if isinstance(attempt, tuple):
                return function(*attempt)
            return function(**attempt)
        except TypeError as exc:
            last_type_error = exc
    if last_type_error:
        raise RuntimeError("Unsupported indico-client method signature.") from last_type_error
    raise RuntimeError("No compatible call signature found.")


def _normalize_record(record: Any) -> IndicoMeeting:
    """Map arbitrary event payloads to IndicoMeeting."""
    event_id = str(_pick(record, "id", "event_id"))
    title = str(_pick(record, "title", "name", default="Untitled meeting"))
    description = str(_pick(record, "description", "summary", default=""))
    url_value = _pick(record, "url", "event_url", default=None)
    start_value = _pick(record, "start_dt", "start_datetime", "start", "startDate")

    if isinstance(start_value, date) and not isinstance(start_value, datetime):
        start_datetime = datetime.combine(start_value, datetime.min.time())
    elif isinstance(start_value, datetime):
        start_datetime = start_value
    elif isinstance(start_value, str):
        start_datetime = datetime.fromisoformat(start_value.replace("Z", "+00:00"))
    else:
        raise ValueError(f"Unsupported event start datetime value: {start_value!r}")

    return IndicoMeeting(
        remote_id=event_id,
        title=title,
        start_datetime=start_datetime,
        description=description,
        url=str(url_value) if url_value is not None else None,
    )


def _pick(record: Any, *keys: str, default: Any = ...) -> Any:
    if isinstance(record, dict):
        for key in keys:
            if key in record:
                return record[key]
    else:
        for key in keys:
            if hasattr(record, key):
                return getattr(record, key)

    if default is ...:
        raise ValueError(
            f"Missing required event keys, expected one of: {', '.join(keys)}"
        )
    return default

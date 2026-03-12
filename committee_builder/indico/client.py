"""Thin CERN Indico HTTP export integration layer."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

from committee_builder.indico.config import IndicoSource


@dataclass(frozen=True)
class IndicoMeeting:
    """Normalized meeting record fetched from Indico."""

    remote_id: str
    title: str
    start_datetime: datetime
    description: str
    participants: list[str]
    documents: list[tuple[str, str]]
    url: str | None


def fetch_meetings(
    source: IndicoSource,
    start_date: date,
    end_date: date,
    api_key_env: str = "INDICO_API_KEY",
    api_token_env: str = "INDICO_API_TOKEN",
) -> list[IndicoMeeting]:
    """Fetch meetings for a source and normalize payloads."""
    payload = _fetch_category_export(
        base_url=source.base_url,
        category_id=source.category_id,
        query_params={
            "from": start_date.isoformat(),
            "to": end_date.isoformat(),
            "detail": "events",
        },
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    meetings = [_normalize_record(record) for record in payload.get("results", [])]
    return [
        _hydrate_meeting_participants(
            meeting,
            api_key_env=api_key_env,
            api_token_env=api_token_env,
        )
        for meeting in meetings
    ]


def fetch_category_title(
    base_url: str,
    category_id: int,
    api_key_env: str = "INDICO_API_KEY",
    api_token_env: str = "INDICO_API_TOKEN",
) -> str:
    """Resolve a category title from Indico."""
    payload = _fetch_category_export(
        base_url=base_url,
        category_id=category_id,
        query_params={"from": "today", "to": "365d"},
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )

    category_paths = payload.get("additionalInfo", {}).get("eventCategories", [])
    for path_entry in category_paths:
        for category in path_entry.get("path", []):
            if str(category.get("id")) == str(category_id):
                category_title = str(category.get("name", "")).strip()
                if category_title:
                    return category_title

    for record in payload.get("results", []):
        category_title = str(record.get("category", "")).strip()
        if category_title:
            return category_title

    category_page_title = _fetch_category_page_title(
        base_url=base_url,
        category_id=category_id,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    if category_page_title:
        return category_page_title

    raise RuntimeError(f"No title returned for category {category_id}.")


def _fetch_category_export(
    base_url: str,
    category_id: int,
    query_params: dict[str, str],
    api_key_env: str,
    api_token_env: str,
) -> dict[str, Any]:
    request_url = f"{base_url.rstrip('/')}/export/categ/{category_id}.json"
    params = dict(query_params)
    params["pretty"] = "yes"
    auth = _build_auth(
        request_url=request_url,
        params=params,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    params.update(auth["params"])

    response = requests.get(
        request_url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "committee-history-builder/0.1",
            **auth["headers"],
        },
    )
    response.raise_for_status()
    return response.json()


def _fetch_event_export(
    base_url: str,
    event_id: str,
    query_params: dict[str, str],
    api_key_env: str,
    api_token_env: str,
) -> dict[str, Any]:
    request_url = f"{base_url.rstrip('/')}/export/event/{event_id}.json"
    params = dict(query_params)
    params["pretty"] = "yes"
    auth = _build_auth(
        request_url=request_url,
        params=params,
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    params.update(auth["params"])

    response = requests.get(
        request_url,
        params=params,
        timeout=30,
        headers={
            "User-Agent": "committee-history-builder/0.1",
            **auth["headers"],
        },
    )
    response.raise_for_status()
    return response.json()


def _fetch_category_page_title(
    base_url: str, category_id: int, api_key_env: str, api_token_env: str
) -> str | None:
    request_url = f"{base_url.rstrip('/')}/category/{category_id}/"
    auth = _build_auth(
        request_url=request_url,
        params={},
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    response = requests.get(
        request_url,
        params=auth["params"],
        timeout=30,
        headers={
            "User-Agent": "committee-history-builder/0.1",
            **auth["headers"],
        },
    )
    response.raise_for_status()

    h1_match = re.search(
        r'<h1 class="category-title">\s*(?:<[^>]+>\s*)*(.*?)\s*(?:</[^>]+>\s*)*</h1>',
        response.text,
        re.DOTALL,
    )
    if h1_match:
        title = re.sub(r"<[^>]+>", "", h1_match.group(1)).strip()
        if title:
            return title

    title_match = re.search(r"<title>(.*?) · Indico</title>", response.text, re.DOTALL)
    if title_match:
        return title_match.group(1).strip()
    return None


def _fetch_event_page(
    event_url: str, api_key_env: str, api_token_env: str
) -> str:
    auth = _build_auth(
        request_url=event_url,
        params={},
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    response = requests.get(
        event_url,
        params=auth["params"],
        timeout=30,
        headers={
            "User-Agent": "committee-history-builder/0.1",
            **auth["headers"],
        },
    )
    response.raise_for_status()
    return response.text


def _build_auth(
    request_url: str,
    params: dict[str, str],
    api_key_env: str,
    api_token_env: str,
) -> dict[str, dict[str, str]]:
    api_key = os.getenv(api_key_env)
    api_token = os.getenv(api_token_env)
    if not api_key and not api_token:
        return {"params": {}, "headers": {}}

    if api_key and api_token:
        timestamp = str(int(time.time()))
        signed_params = dict(params)
        signed_params["ak"] = api_key
        signed_params["timestamp"] = timestamp
        signed_params["signature"] = _generate_signature(
            request_url=request_url,
            params=signed_params,
            secret_key=api_token,
        )
        return {"params": signed_params, "headers": {}}

    if api_key:
        return {"params": {"ak": api_key}, "headers": {}}

    return {"params": {}, "headers": {"Authorization": f"Bearer {api_token}"}}


def _generate_signature(
    request_url: str, params: dict[str, str], secret_key: str
) -> str:
    canonical_query = urlencode(sorted(params.items()))
    parsed = urlsplit(request_url)
    string_to_sign = f"{parsed.path}?{canonical_query}"
    digest = hmac.new(
        secret_key.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha1,
    ).hexdigest()
    return digest


def _normalize_record(record: Any) -> IndicoMeeting:
    """Map arbitrary event payloads to IndicoMeeting."""
    event_id = str(_pick(record, "id", "event_id"))
    title = str(_pick(record, "title", "name", default="Untitled meeting"))
    description = str(_pick(record, "description", "summary", default=""))
    url_value = _pick(record, "url", "event_url", default=None)
    start_value = _pick(record, "start_dt", "start_datetime", "start", "startDate")

    if isinstance(start_value, dict):
        date_value = start_value.get("date")
        time_value = start_value.get("time", "00:00:00")
        timezone_value = start_value.get("tz")
        if date_value is None:
            raise ValueError(f"Unsupported event start datetime value: {start_value!r}")
        iso_value = f"{date_value}T{time_value}"
        start_datetime = datetime.fromisoformat(iso_value)
        if timezone_value:
            # Keep timezone name available in ISO-like form without introducing extra deps.
            start_datetime = datetime.fromisoformat(iso_value)
    elif isinstance(start_value, date) and not isinstance(start_value, datetime):
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
        participants=_extract_participants(record),
        documents=[],
        url=str(url_value) if url_value is not None else None,
    )


def _hydrate_meeting_participants(
    meeting: IndicoMeeting,
    api_key_env: str,
    api_token_env: str,
) -> IndicoMeeting:
    if meeting.url is None:
        return meeting

    parsed_url = urlsplit(meeting.url)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    payload = _fetch_event_export(
        base_url=base_url,
        event_id=meeting.remote_id,
        query_params={"detail": "contributions"},
        api_key_env=api_key_env,
        api_token_env=api_token_env,
    )
    results = payload.get("results", [])
    if not results:
        return meeting

    participants = _dedupe_names(
        [*meeting.participants, *_extract_participants(results[0])]
    )
    documents = _extract_documents(
        _fetch_event_page(
            meeting.url,
            api_key_env=api_key_env,
            api_token_env=api_token_env,
        ),
        base_url=base_url,
    )
    return IndicoMeeting(
        remote_id=meeting.remote_id,
        title=meeting.title,
        start_datetime=meeting.start_datetime,
        description=meeting.description,
        participants=participants,
        documents=documents,
        url=meeting.url,
    )


def _extract_participants(record: Any) -> list[str]:
    names = _dedupe_names(_collect_names(record))
    return names


def _collect_names(value: Any, parent_key: str = "") -> list[str]:
    if isinstance(value, dict):
        direct_name = _name_from_person_dict(value, parent_key)
        names = [direct_name] if direct_name else []
        for key, child in value.items():
            lowered_key = key.lower()
            if lowered_key in {
                "chairs",
                "contributions",
                "speakers",
                "speaker",
                "presenters",
                "presenter",
                "persons",
                "person",
                "session",
                "sessions",
                "subcontributions",
                "authors",
                "primaryauthors",
                "coauthors",
            }:
                names.extend(_collect_names(child, lowered_key))
        return names

    if isinstance(value, list):
        names: list[str] = []
        for item in value:
            names.extend(_collect_names(item, parent_key))
        return names

    return []


def _name_from_person_dict(value: dict[str, Any], parent_key: str) -> str | None:
    if parent_key == "contributions" and "title" in value:
        return None

    for key in ("fullName", "full_name", "name"):
        raw_name = value.get(key)
        if isinstance(raw_name, str):
            normalized = _normalize_name(raw_name)
            if normalized:
                return normalized

    first_name = value.get("first_name")
    last_name = value.get("last_name")
    if isinstance(first_name, str) and isinstance(last_name, str):
        normalized = _normalize_name(f"{first_name} {last_name}")
        if normalized:
            return normalized

    return None


def _normalize_name(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ,")
    if not cleaned:
        return ""

    if "," in cleaned:
        pieces = [piece.strip() for piece in cleaned.split(",", maxsplit=1)]
        if len(pieces) == 2 and all(pieces):
            cleaned = f"{pieces[1]} {pieces[0]}"
    return cleaned


def _dedupe_names(values: list[str]) -> list[str]:
    unique_names: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = _normalize_name(value)
        if not normalized:
            continue
        folded = normalized.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        unique_names.append(normalized)
    return unique_names


def _extract_documents(event_html: str, base_url: str) -> list[tuple[str, str]]:
    matches = re.findall(
        r'<a[^>]+class="[^"]*\battachment\b[^"]*"[^>]+href="([^"]+)"[^>]*title="([^"]+)"',
        event_html,
        flags=re.IGNORECASE,
    )
    documents: list[tuple[str, str]] = []
    seen: set[str] = set()
    for href, title in matches:
        absolute_url = href if href.startswith("http") else f"{base_url}{href}"
        folded = absolute_url.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        documents.append((title.strip(), absolute_url))
    return documents


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

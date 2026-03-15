"""Thin CERN Indico HTTP export integration layer."""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
from urllib.parse import urlencode, urlsplit

import requests

from committee_builder.indico.config import IndicoSource
from committee_builder.indico.credentials import normalize_base_url, resolve_stored_api_key


@dataclass(frozen=True)
class IndicoDocument:
    """Normalized document reference associated with an event or contribution."""

    label: str
    url: str
    talk_title: str | None = None
    speaker_names: list[str] = field(default_factory=list)
    sort_key: tuple[int, ...] = field(
        default_factory=lambda: (1, 0, 0), repr=False, compare=False
    )


@dataclass(frozen=True)
class IndicoContribution:
    """Normalized contribution details for a meeting agenda entry."""

    title: str
    speaker_names: list[str] = field(default_factory=list)
    documents: list[IndicoDocument] = field(default_factory=list)
    minutes: str = ""
    sort_key: tuple[int, ...] = field(default_factory=lambda: (2, 0), repr=False)


@dataclass(frozen=True)
class IndicoMeeting:
    """Normalized meeting record fetched from Indico."""

    remote_id: str
    title: str
    start_datetime: datetime
    description: str
    participants: list[str]
    documents: list[IndicoDocument]
    url: str | None
    minutes: str = ""
    contributions: list[IndicoContribution] = field(default_factory=list)


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
    base_url = _base_url_from_request_url(request_url)
    explicit_api_key = os.getenv(api_key_env)
    explicit_api_token = os.getenv(api_token_env)
    stored_api_token = None
    if not explicit_api_key and not explicit_api_token:
        stored_api_token = resolve_stored_api_key(base_url)

    api_key = explicit_api_key
    api_token = explicit_api_token or stored_api_token
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


def _base_url_from_request_url(request_url: str) -> str:
    parsed = urlsplit(request_url)
    path = parsed.path

    for marker in ("/export/", "/category/", "/event/"):
        if marker in path:
            prefix = path.split(marker, 1)[0]
            return normalize_base_url(f"{parsed.scheme}://{parsed.netloc}{prefix}")

    return normalize_base_url(f"{parsed.scheme}://{parsed.netloc}")


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
        minutes=_extract_minutes(record),
        participants=_extract_participants(record),
        documents=[],
        contributions=[],
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
    base_url = _base_url_from_request_url(meeting.url)
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
    contributions = _extract_contributions(results[0], base_url=base_url)
    contribution_documents = [
        document
        for contribution in contributions
        for document in contribution.documents
    ]
    return IndicoMeeting(
        remote_id=meeting.remote_id,
        title=meeting.title,
        start_datetime=meeting.start_datetime,
        description=meeting.description,
        minutes=_extract_minutes(results[0]) or meeting.minutes,
        participants=participants,
        documents=_merge_documents(contribution_documents, documents),
        contributions=contributions,
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


def _extract_documents(event_html: str, base_url: str) -> list[IndicoDocument]:
    matches = re.findall(
        r'<a[^>]+class="[^"]*\battachment\b[^"]*"[^>]+href="([^"]+)"[^>]*title="([^"]+)"',
        event_html,
        flags=re.IGNORECASE,
    )
    documents: list[IndicoDocument] = []
    seen: set[str] = set()
    for href, title in matches:
        absolute_url = _absolute_url(href, base_url)
        folded = absolute_url.casefold()
        if folded in seen:
            continue
        seen.add(folded)
        documents.append(IndicoDocument(label=title.strip(), url=absolute_url))
    return documents


def _extract_contribution_documents(
    record: Any, base_url: str
) -> list[IndicoDocument]:
    return [
        document
        for contribution in _extract_contributions(record, base_url)
        for document in contribution.documents
    ]


def _extract_contributions(
    record: Any, base_url: str
) -> list[IndicoContribution]:
    contributions = record.get("contributions", []) if isinstance(record, dict) else []
    extracted: list[IndicoContribution] = []
    sorted_contributions = sorted(
        enumerate(contributions),
        key=lambda item: _contribution_sort_key(item[1], fallback_index=item[0]),
    )
    for contribution_position, (_, contribution) in enumerate(sorted_contributions):
        if not isinstance(contribution, dict):
            continue
        talk_title = str(contribution.get("title", "")).strip() or None
        speaker_names = _extract_participants(contribution)
        documents: list[IndicoDocument] = []
        for attachment_index, (label, url) in enumerate(
            _collect_attachment_links(contribution, base_url)
        ):
            documents.append(
                IndicoDocument(
                    label=label,
                    url=url,
                    talk_title=talk_title,
                    speaker_names=speaker_names,
                    sort_key=(0, contribution_position, attachment_index),
                )
            )
        extracted.append(
            IndicoContribution(
                title=talk_title or "Untitled talk",
                speaker_names=speaker_names,
                documents=_dedupe_document_list(documents),
                minutes=_extract_minutes(contribution),
                sort_key=(0, contribution_position),
            )
        )
    return extracted


_MINUTES_FIELD_CANDIDATES = (
    "minutes",
    "minute",
    "meeting_minutes",
    "meetingMinutes",
    "minutes_html",
    "minutesHtml",
    "minutes_text",
    "minutesText",
    "minute_text",
    "minuteText",
    "note",
    "notes",
    "meeting_note",
    "meetingNote",
    "meeting_notes",
    "meetingNotes",
    "note_html",
    "noteHtml",
    "notes_html",
    "notesHtml",
    "note_text",
    "noteText",
    "notes_text",
    "notesText",
)

_MINUTES_CONTENT_KEYS = (
    "html",
    "rendered_html",
    "renderedHtml",
    "markdown",
    "md",
    "text",
    "value",
    "content",
    "source",
)

_MINUTES_EXCLUDED_CONTAINERS = {
    "attachments",
    "attachment",
    "materials",
    "material",
    "files",
    "resources",
    "documents",
    "contributions",
    "subcontributions",
}


def _extract_minutes(record: Any) -> str:
    return _extract_minutes_from_value(record, parent_key="")


def _extract_minutes_from_value(value: Any, parent_key: str) -> str:
    if isinstance(value, list):
        fragments = [
            _extract_minutes_from_value(item, parent_key=parent_key).strip()
            for item in value
        ]
        return "\n\n".join(fragment for fragment in fragments if fragment)

    if not isinstance(value, dict):
        return ""

    if parent_key.casefold() in _MINUTES_EXCLUDED_CONTAINERS:
        return ""

    for key in _MINUTES_FIELD_CANDIDATES:
        if key not in value:
            continue
        rendered = _extract_minutes_payload(value[key])
        if rendered:
            return rendered

    for key, child in value.items():
        if not isinstance(child, (dict, list)):
            continue
        rendered = _extract_minutes_from_value(child, parent_key=str(key))
        if rendered:
            return rendered
    return ""


def _extract_minutes_payload(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()

    if isinstance(value, list):
        fragments = [_extract_minutes_payload(item) for item in value]
        return "\n\n".join(fragment for fragment in fragments if fragment)

    if not isinstance(value, dict):
        return ""

    for key in _MINUTES_CONTENT_KEYS:
        candidate = value.get(key)
        if isinstance(candidate, str) and candidate.strip():
            return candidate.strip()

    for child in value.values():
        rendered = _extract_minutes_payload(child)
        if rendered:
            return rendered
    return ""


def _collect_attachment_links(
    value: Any, base_url: str, parent_key: str = ""
) -> list[tuple[str, str]]:
    if isinstance(value, list):
        documents: list[tuple[str, str]] = []
        for item in value:
            documents.extend(_collect_attachment_links(item, base_url, parent_key))
        return documents

    if not isinstance(value, dict):
        return []

    documents: list[tuple[str, str]] = []
    lowered_parent = parent_key.lower()
    if _looks_like_attachment_record(value, lowered_parent):
        label = _pick_first_string(value, "filename", "fileName", "title", "name", "label")
        href = _pick_first_string(
            value, "download_url", "downloadUrl", "href", "url", "link_url", "linkUrl"
        )
        if label and href:
            documents.append((label, _absolute_url(href, base_url)))

    for key, child in value.items():
        documents.extend(_collect_attachment_links(child, base_url, str(key)))
    return documents


def _looks_like_attachment_record(value: dict[str, Any], parent_key: str) -> bool:
    if parent_key in {"attachments", "attachment", "materials", "material", "files", "resources"}:
        return True
    return any(
        key in value
        for key in ("download_url", "downloadUrl", "filename", "fileName", "mimeType", "contentType")
    )


def _pick_first_string(value: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        candidate = value.get(key)
        if isinstance(candidate, str):
            normalized = candidate.strip()
            if normalized:
                return normalized
    return None


def _absolute_url(url: str, base_url: str) -> str:
    return url if url.startswith("http") else f"{base_url}{url}"


def _merge_documents(*document_groups: list[IndicoDocument]) -> list[IndicoDocument]:
    merged: list[IndicoDocument] = []
    seen: set[str] = set()
    for document_group in document_groups:
        for document in document_group:
            folded = document.url.casefold()
            if folded in seen:
                continue
            seen.add(folded)
            merged = _merge_document_candidate(merged, document)
    return sorted(_dedupe_document_list(merged), key=lambda document: document.sort_key)


def _dedupe_document_list(documents: list[IndicoDocument]) -> list[IndicoDocument]:
    deduped: list[IndicoDocument] = []
    for document in documents:
        deduped = _merge_document_candidate(deduped, document)
    return deduped


def _merge_document_candidate(
    existing_documents: list[IndicoDocument], candidate: IndicoDocument
) -> list[IndicoDocument]:
    for index, existing in enumerate(existing_documents):
        if existing.url.casefold() == candidate.url.casefold():
            if _document_rank(candidate) > _document_rank(existing):
                existing_documents[index] = candidate
            return existing_documents
        if _same_logical_document(existing, candidate):
            existing_documents[index] = _prefer_document(existing, candidate)
            return existing_documents

    existing_documents.append(candidate)
    return existing_documents


def _same_logical_document(left: IndicoDocument, right: IndicoDocument) -> bool:
    if left.label.casefold() != right.label.casefold():
        return False

    left_talk = (left.talk_title or "").casefold()
    right_talk = (right.talk_title or "").casefold()
    if left_talk and right_talk:
        return left_talk == right_talk

    if left_talk or right_talk:
        return True

    return tuple(name.casefold() for name in left.speaker_names) == tuple(
        name.casefold() for name in right.speaker_names
    )


def _prefer_document(left: IndicoDocument, right: IndicoDocument) -> IndicoDocument:
    preferred = left if _document_rank(left) >= _document_rank(right) else right
    fallback = right if preferred is left else left
    metadata_source = preferred if _document_context_rank(preferred) >= _document_context_rank(fallback) else fallback
    url_source = preferred if _document_url_rank(preferred) >= _document_url_rank(fallback) else fallback
    return IndicoDocument(
        label=metadata_source.label or url_source.label,
        url=url_source.url,
        talk_title=metadata_source.talk_title or fallback.talk_title,
        speaker_names=metadata_source.speaker_names or fallback.speaker_names,
        sort_key=preferred.sort_key if preferred.sort_key <= fallback.sort_key else fallback.sort_key,
    )


def _document_rank(document: IndicoDocument) -> tuple[int, int]:
    return (_document_context_rank(document), _document_url_rank(document))


def _document_context_rank(document: IndicoDocument) -> int:
    return int(bool(document.talk_title or document.speaker_names))


def _document_url_rank(document: IndicoDocument) -> int:
    return int(not _looks_like_indico_redirect(document.url))


def _looks_like_indico_redirect(url: str) -> bool:
    return bool(re.search(r"/attachments/\d+/\d+/go(?:$|[?#])", url))


def _contribution_sort_key(contribution: Any, fallback_index: int) -> tuple[int, ...]:
    if not isinstance(contribution, dict):
        return (2, fallback_index)

    start_value = _pick(
        contribution,
        "start_dt",
        "start_datetime",
        "start",
        "startDate",
        default=None,
    )
    normalized_start = _normalize_sort_datetime(start_value)
    if normalized_start is not None:
        return (0, *normalized_start)

    contribution_id = _pick(contribution, "id", "contributionId", default=None)
    if contribution_id is not None:
        numeric = _parse_int(contribution_id)
        if numeric is not None:
            return (1, numeric)
        return (1, fallback_index, str(contribution_id))

    return (2, fallback_index)


def _normalize_sort_datetime(value: Any) -> tuple[int, int, int, int, int, int] | None:
    if isinstance(value, dict):
        date_value = value.get("date")
        if not isinstance(date_value, str) or not date_value:
            return None
        time_value = value.get("time", "00:00:00")
        if not isinstance(time_value, str) or not time_value:
            time_value = "00:00:00"
        normalized = f"{date_value}T{time_value}".replace("Z", "+00:00")
    elif isinstance(value, datetime):
        normalized = value.isoformat()
    elif isinstance(value, date):
        normalized = f"{value.isoformat()}T00:00:00"
    elif isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
    else:
        return None

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return (
        parsed.year,
        parsed.month,
        parsed.day,
        parsed.hour,
        parsed.minute,
        parsed.second,
    )


def _parse_int(value: Any) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


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

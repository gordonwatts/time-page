## Indico ingestion architecture (fetch during build)

This document describes the current architecture where Indico categories are configured in the main project YAML and fetched during `committee build`.

## Master project file model

- A single project YAML is the source of truth for:
  - project metadata
  - date window
  - local events
  - `indico_category_sources`
- Build does **not** require a separate generated meetings YAML.
- Legacy field names are still migrated for compatibility (`committee` -> `metadata` + `date_window`, `sources` -> `indico_category_sources`).

## Runtime flow

1. Load and validate project YAML.
2. Resolve the effective date window.
3. Fetch meetings from every configured `indico_category_sources` entry for that window.
4. Convert remote meeting payloads to `events` (including markdown conversion and contribution/document extraction).
5. Merge imported events with local events.
   - Collision rule: local YAML event wins when IDs match.
6. Render markdown and generate a standalone HTML page.

## Date precedence (with explicit examples)

Effective build date window precedence:

1. CLI absolute range `--from` + `--to`
2. CLI relative range `--past-weeks` + `--future-weeks`
3. Project file `date_window.start_date` + `date_window.end_date`
4. Default fallback when no explicit end date exists: today ± 1 week

Examples:

- `committee build project.yaml` with YAML window `2024-01-01`..`2024-12-31` uses **2024-01-01** to **2024-12-31**.
- `committee build project.yaml --from 2025-01-01 --to 2025-03-31` uses **2025-01-01** to **2025-03-31**.
- `committee build project.yaml --past-weeks 2 --future-weeks 4` uses **today - 2 weeks** to **today + 4 weeks**.
- If YAML has only `start_date` and no `end_date`, `committee build project.yaml` falls back to **today - 1 week** through **today + 1 week**.

## Warning fallback behavior

The build pipeline prefers continuing with warnings when possible:

- Missing `date_window.end_date` (and no CLI overrides): logs a warning and uses today ± 1 week.
- Auth-required source without usable credentials: logs warning, skips that source, continues.
- Imported event ID duplicates local event ID: logs warning, keeps local event.

These warnings are visible by default and are easier to inspect with `committee -v` or `committee -vv`.

## Command implications

- `committee build <project.yaml>` is the primary ingestion/build command.
- Use `committee build --from YYYY-MM-DD --to YYYY-MM-DD` (or relative week options) to override ingest date windows.
- `committee indico add|list|remove|api-key` manage source metadata and credentials.

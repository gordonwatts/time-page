# Committee History Builder

Python-first CLI for generating a single standalone committee-history HTML page from a master YAML project file.

## What it does

- Uses one YAML project file as the source of truth (local events + Indico category sources)
- Validates schema and semantic rules
- Renders markdown fields (including dollar-math syntax)
- Fetches Indico meetings during `build`, then merges imported events with local events
- Generates a self-contained HTML file with inlined CSS, JS, and data

## Install

```bash
python -m venv .venv
. .venv/Scripts/activate  # PowerShell: .venv\\Scripts\\Activate.ps1
pip install -e .
```

Optional dev tools:

```bash
pip install -e .[dev]
```

## Run with `uvx` (no local install)

Prerequisite: install `uv` on the machine ([docs](https://docs.astral.sh/uv/)).

```bash
uvx --from . committee --help
uvx --from . committee build examples/committee.example.yaml --overwrite
```

## Quickstart

1. Create a blank master project file:

```bash
committee init data/committee.project.yaml
```

2. Add an Indico category source (optional):

```bash
committee indico add data/committee.project.yaml https://indico.example.org/category/1234/ --title cern
```

3. Validate the project file:

```bash
committee validate data/committee.project.yaml
```

4. Build standalone page (this step also fetches Indico meetings for the effective date window):

```bash
committee build data/committee.project.yaml --overwrite
```

By default this writes:

```text
data/committee.project.html
```

## CLI commands

- `committee build PROJECT_YAML [--output PATH] [--overwrite] [--from DATE_EXPR --to DATE_EXPR] [--past-weeks N --future-weeks M]`
- `committee validate PROJECT_YAML`
- `committee init PATH [--force] [--title TEXT] [--from DATE_EXPR] [--to DATE_EXPR]`
- `committee add event PROJECT_YAML ...`
- `committee add indico PROJECT_YAML CATEGORY_URL [--title TITLE]`
- `committee add minutes PROJECT_YAML EVENT_ID MINUTES_PATH [--mode append|replace] [--target event|contribution] [--contribution-index N] [--contribution-title TITLE]`
- `committee indico add PROJECT_YAML CATEGORY_URL [--title TITLE] [--title-match PATTERN] [--title-exclude PATTERN] [--color COLOR] [--api-key-env ENV] [--api-token-env ENV]`
- `committee indico list PROJECT_YAML`
- `committee indico remove PROJECT_YAML SOURCE_NAME`
- `committee indico api-key BASE_URL TOKEN [--api-key-env ENV]`

## Indico workflow (single master project file)

1. Add one or more category sources to the same project file:

```bash
committee indico add data/committee.project.yaml https://indico.example.org/category/1234/ --title cern --color '#FCA5A5'
committee indico add data/committee.project.yaml https://indico.example.org/category/5678/ --title lhcb
```

2. Optionally narrow imported meeting titles by regex:

```bash
committee indico add data/committee.project.yaml https://indico.example.org/category/1234/ --title cern --title-match LUP --title-exclude "high school"
```

3. Build. During build, configured sources are fetched and merged into the in-memory history before rendering:

```bash
committee build data/committee.project.yaml --from 2024-01-01 --to 2024-12-31 --overwrite
committee build data/committee.project.yaml --from -3w --to now --overwrite
```

Use `committee build` with `--from/--to` (or `--past-weeks/--future-weeks`) whenever you need date overrides for Indico ingestion. `--from` and `--to` accept ISO dates, natural-language expressions that `dateparser` understands, and short relative forms such as `now`, `-3d`, `+2w`, `-1m`, and `-1y`.

### Date precedence and fallback behavior

Effective build date window precedence is:

1. CLI absolute range `--from` + `--to`
2. CLI relative range `--past-weeks` + `--future-weeks`
3. `date_window` in project YAML
4. Default fallback: today ± 1 week, with a warning log

Explicit examples:

- If YAML has `start_date: 2024-01-01` and `end_date: 2024-12-31`, then `committee build project.yaml` uses **2024-01-01 through 2024-12-31**.
- `committee build project.yaml --from 2025-01-01 --to 2025-03-31` overrides YAML and uses **2025-01-01 through 2025-03-31**.
- `committee build project.yaml --from -3d --to now` uses **three days ago through today**.
- `committee build project.yaml --past-weeks 3 --future-weeks 1` uses **today - 3 weeks** through **today + 1 week**.
- If YAML omits `end_date`, and no CLI range is supplied, build falls back to **today - 1 week** through **today + 1 week** and logs a warning.

YAML `date_window.start_date` and `date_window.end_date` accept the same flexible expressions, so a project file can use values like `"2025-03-20"`, `"-2w"`, or `"now"`.

Other warning fallbacks to know:

- If an Indico source requires auth and credentials are unavailable/invalid, that source is skipped with a warning while build continues.
- If an imported event ID collides with a local event ID, local YAML wins and the imported record is skipped with a warning.

## Logging and verbosity

Use global verbosity flags:

- default: warnings/errors only
- `-v`: info logging
- `-vv`: debug logging

Examples:

```bash
committee -v validate data/committee.project.yaml
committee -vv build data/committee.project.yaml
```

## Source schema overview

Top-level keys in the master project file:

- `schema_version`
- `metadata`
- `date_window`
- `event_type_styles`
- `events`
- `indico_category_sources`

Markdown-capable fields:

- `metadata.description_md`
- `metadata.notes_md`
- `events[].summary_md`
- `events[].minutes_md`
- `events[].contributions[].minutes_md`

See a complete sample at [examples/committee.example.yaml](examples/committee.example.yaml).

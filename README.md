# Committee History Builder

Python-first CLI for generating a single standalone committee-history HTML page from an editable YAML source file.

## What it does

- Uses YAML as the source of truth
- Validates schema and semantic rules
- Renders markdown fields (including dollar-math syntax)
- Generates a self-contained HTML file with inlined CSS, JS, and data
- No backend and no runtime fetches required

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

Run directly from a local checkout:

```bash
uvx --from . committee --help
uvx --from . committee build examples/committee.example.yaml --overwrite
```

Run directly from this GitHub repo:

```bash
uvx --from git+https://github.com/gordonwatts/time-page.git committee --help
```

Run from a published package (recommended for "any computer" usage):

```bash
uvx --from committee-history-builder committee --help
```

## Gaps to close for true "any computer" `uvx` usage

- Publish `committee-history-builder` to PyPI (or another index) so users can run `uvx --from committee-history-builder ...` without cloning the repo.
- Add a CI smoke test that runs `uvx --from . committee --help` (and optionally `uvx --from committee-history-builder committee --help` after publish) to prevent packaging/entry-point regressions.

## Quickstart

Create a starter file:

```bash
committee init data/committee.history.yaml
```

Validate data:

```bash
committee validate data/committee.history.yaml
```

Build standalone page:

```bash
committee build data/committee.history.yaml
```

By default this writes:

```text
data/committee.history.html
```

Override output path:

```bash
committee build data/committee.history.yaml --output dist/committee-history.html --overwrite
```

## CLI commands

- `committee build INPUT_YAML [--output PATH] [--overwrite]`
- `committee validate INPUT_YAML`
- `committee init PATH [--force]`
- `committee import-csv` (placeholder)
- `committee import-md` (placeholder)
- `committee indico add CONFIG CATEGORY_URL [--title TITLE] [--color COLOR] [--api-key-env ENV] [--api-token-env ENV]`
- `committee indico list CONFIG`
- `committee indico remove CONFIG NAME`
- `committee indico generate CONFIG PROJECT_YAML --from YYYY-MM-DD --to YYYY-MM-DD [--api-key-env ENV] [--api-token-env ENV] [--output PATH]`

### Indico source workflow

The Indico commands use the standard HTTP export API. Public categories work without credentials; if API credentials are present they are used automatically.

```bash
pip install -e .
```

Configure a source:

```bash
committee indico add cern https://indico.example.org/category/1234/ --title cern --color red
```

If `--color` is omitted, the CLI assigns a unique pale hex color automatically. Named CSS colors and hex values are normalized to stored `#RRGGBB` source colors.

Generate meeting events into a new YAML file:

```bash
committee indico generate cern data/committee.history.yaml --from 2024-01-01 --to 2024-12-31
```

You can also generate with a relative range:

```bash
committee indico generate cern data/committee.history.yaml --past-weeks 3 --future-weeks 1
```

See command help:

```bash
committee --help
committee build --help
```

## Logging and verbosity

Use global verbosity flags:

- default: warnings/errors only
- `-v`: info logging
- `-vv`: debug logging

Examples:

```bash
committee -v validate data/committee.history.yaml
committee -vv build data/committee.history.yaml
```

All informational and warning output is emitted through the Python `logging` package.

## Source schema overview

Top-level keys:

- `schema_version`
- `committee`
- `event_type_styles`
- `events`

Markdown-capable fields:

- `committee.description_md`
- `committee.notes_md`
- `events[].summary_md`

Events require at least:

- `id`, `type`, `title`, `date`, `important`, `summary_md`

Documents are records:

- `{ label: string, url?: string }`

See a complete sample at [examples/committee.example.yaml](examples/committee.example.yaml).

## Build architecture

1. Load YAML
2. Validate with Pydantic + semantic checks
3. Normalize event order
4. Render markdown/math to HTML
5. Render Jinja2 template with inlined CSS/JS/data
6. Write one standalone HTML file

## Troubleshooting

Validation errors:

- Run `committee -vv validate <file>` for richer diagnostics.
- Confirm required keys exist and dates are `YYYY-MM-DD`.

Build fails because output exists:

- Re-run with `--overwrite`.

Math not rendering as expected:

- Use `$...$` for inline and `$$...$$` for block expressions.
- Ensure backslashes in YAML block strings are escaped where needed.


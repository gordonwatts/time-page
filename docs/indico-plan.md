## Proposed Indico ingestion workflow (planning)

This section captures the planned implementation for importing meetings from Indico categories and producing YAML files that are directly ingestable by `committee build`.

### Required dependency and docs source

- Use the **official Python package**: `indico-client` (PyPI: https://pypi.org/project/indico-client/).
- Use the **official product documentation** for implementation details and authentication patterns: https://developer.indicodata.ai/docs/getting-started.
- Do **not** implement direct ad-hoc HTTP calls when equivalent functionality exists in `indico-client`; the client library is the primary integration path.

### CLI and config goals

1. Add a project-local config file (e.g. `.committee.indico.yaml`) to track multiple Indico category sources.
2. Add source management commands:
   - `committee sources add`
   - `committee sources list`
   - `committee sources remove`
3. Add meeting generation command:
   - `committee meetings generate --from YYYY-MM-DD --to YYYY-MM-DD`
   - convenience ranges like `--past-weeks 3 --future-weeks 1`

### Authentication approach

- Support private feeds by reading credentials from environment variables.
- Config stores env-var names (for example `INDICO_API_KEY`, `INDICO_API_TOKEN`) rather than raw secrets.
- The command resolves env vars at runtime and initializes `indico-client` with those credentials.

### Output contract

- Generated YAML must validate against existing schema and be directly consumable by:
  - `committee validate <generated.yaml>`
  - `committee build <generated.yaml>`
- Event mapping should be deterministic:
  - stable generated IDs (`<source-name>-<remote-id>`)
  - normalized date handling
  - sorted output for low-noise diffs.

### High-level implementation phases

1. Add typed config models and YAML IO support for Indico source configuration.
2. Implement source-management CLI commands.
3. Implement Indico integration layer using `indico-client`.
4. Implement transformation from fetched meetings to `CommitteeHistory` schema events.
5. Implement `meetings generate` command with absolute and relative date range options.
6. Add pytest coverage for config operations, API client mocking, and generated YAML compatibility.
7. Update README usage examples end-to-end.

## Proposed Indico ingestion workflow (planning)

This section captures the planned implementation for importing meetings from Indico categories and producing YAML files that are directly ingestable by `committee build`.

### Required dependency and docs source

- Use the **official Python package**: `indico-client` (PyPI: https://pypi.org/project/indico-client/).
- Use the **official product documentation** for implementation details and authentication patterns: https://developer.indicodata.ai/docs/getting-started.
- Do **not** implement direct ad-hoc HTTP calls when equivalent functionality exists in `indico-client`; the client library is the primary integration path.

### CLI and config goals

1. Add a project config file (e.g. `.committee.indico.yaml`) to track multiple Indico category sources.
   - User can have multiple project files - so the project file needs to be specified by the user for all project related commands.
3. Add source management commands:
   - `committee sources add`
   - `committee sources list`
   - `committee sources remove`
4. Add meeting generation command - to output a yaml file with a meetings list:
   - `committee sources generate project.yaml --from YYYY-MM-DD --to YYYY-MM-DD` - default output will be `project-meetings.yaml`, or `--output`.
   - convenience ranges like `--past-weeks 3 --future-weeks 1`

### Authentication approach

- Support private feeds by reading credentials from environment variables or a .env file in the home directory.
- Config stores env-var names (for example `INDICO_API_KEY`, `INDICO_API_TOKEN`) rather than raw secrets.
- The command resolves env vars at runtime and initializes `indico-client` with those credentials.

### Output contract

- Generated YAML (`project-meetings.yaml`) must validate against existing schema and be directly consumable by:
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

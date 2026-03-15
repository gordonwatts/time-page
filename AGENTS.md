# Agent Notes

## Running tests

- Use `.\\.venv\\Scripts\\python.exe -m pytest` from the repo root.
- Do not work around temp-directory sandbox issues with ad hoc env vars or wrapper commands; the repo test harness in `tests/conftest.py` already redirects temp usage safely and cleans up after itself.
- A successful or failing pytest run should not leave `test-scratch/` behind. If `test-scratch/` exists after pytest exits, treat that as a test infrastructure problem.
- `.pytest_cache/` may still exist as a normal repo-local cache directory, but pytest is configured with `-p no:cacheprovider`, so cache behavior should not be required for test runs here.

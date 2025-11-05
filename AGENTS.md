# Repository Guidelines

## Project Structure & Module Organization
MeetHub targets Python 3.11. Core scheduling, polling, and transcription code lives in `src/`, with CLI entry points in `src/cli.py`, orchestrators in `src/main.py`, and shared helpers in `src/services` and `src/utils`. Database models and settings schemas sit under `src/models`. Migrations live in `alembic/`, while reference configs and specs stay in `config/`, `specs/`, and `data/`. Tests are split by scope in `tests/unit`, `tests/integration`, `tests/e2e`, and `tests/contract`; place new cases alongside their peers.

## Build, Test, and Development Commands
Create a virtual environment with `python3 -m venv venv && source venv/bin/activate`, then install dependencies via `pip install -r requirements.txt`. Run the service locally with `LOG_FORMAT=console python -m src.main`, and use `python -m src.cli test-auth` or `test-classification` for spot checks. Apply schema updates using `alembic upgrade head`, and validate the container build with `docker-compose up -d` plus `docker-compose logs -f meethub`.

## Coding Style & Naming Conventions
Format Python with Black (`black .`) and lint with Ruff (`ruff check .`); both use a 100-character line limit. Mypy runs in strict mode, so provide explicit types and avoid implicit `Any`. Follow conventional names: packages and functions `snake_case`, classes `PascalCase`, constants `UPPER_CASE`. Use four-space indentation, keep logging structured through `structlog`, and load configuration through typed settings instead of module-level globals.

## Testing Guidelines
Pytest loads its settings from `pytest.ini`, discovering `test_*.py` and reporting coverage via `--cov=src --cov-report=term-missing`. Reserve `@pytest.mark.integration` and `@pytest.mark.e2e` for long-running scenarios. Default checks should pass with `pytest`; narrower suites can use `pytest -m "integration"` or `pytest -m "not integration"`. Keep fixtures under `tests/fixtures` reusable, and extend contract coverage when public API behavior changes.

## Commit & Pull Request Guidelines
Git history currently mirrors a template baseline, so use concise, imperative commit subjects (e.g., `feat: add drive uploader`) and add a short body when context is non-obvious. Each pull request should cover behaviour changes, link issues, summarize configuration updates, and paste results from `pytest` or relevant CLI commands. Attach screenshots or terminal snippets when `src/ui` or CLI output changes.

## Security & Configuration Tips
Never commit secrets like `service-account.json`, `credentials.json`, or populated `.env` files; share them through the existing secure channels. Document updates to `project_folders.json` and `classification_rules.json`, and keep per-environment overrides inside `config/` rather than code. When rotating keys, re-run `python -m src.cli show-config` to confirm the runtime view before shipping.

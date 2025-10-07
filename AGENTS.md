# Repository Guidelines

## Project Structure & Module Organization
The workspace is managed by uv and contains two installable packages: `pyama-core` (processing logic under `pyama-core/src/pyama_core`) and `pyama-qt` (Qt GUI under `pyama-qt/src/pyama_qt`). Shared integration tests live in `tests/`, and sample assets sit in `data/`. Keep automation scripts, notebooks, and large outputs out of package `src/` trees to preserve clean wheels.

## Build, Test, and Development Commands
Run `uv sync --all-extras` to materialize dev tooling, then install both packages in editable mode via `uv pip install -e pyama-core/` and `uv pip install -e pyama-qt/`. Launch the GUI with `uv run pyama-qt`. Core validation commands: `uv run pytest` (full suite), `uv run python tests/test_workflow.py` (end-to-end pipeline smoke), `uv run ruff check` / `uv run ruff format` (lint + formatting), and `uv run ty` (static typing). Execute commands from the repository root so workspace paths resolve.

## Coding Style & Naming Conventions
Python uses 4-space indentation, type hints, and snake_case for modules, packages, and functions (see `pyama_core.processing.workflow.pipeline`). Prefer `pathlib.Path` for filesystem work and keep logging via module-level loggers. Ruff enforces linting; resolve warnings rather than silencing them. When adding Qt code, respect the MVC guidance in `MVC.md`: views emit signals, controllers orchestrate, models own state.

## Testing Guidelines
Target pytest-based tests under `tests/` or the relevant package mirror. Name files `test_*.py`, and structure fixtures to reuse workflow contexts. Expand coverage with focused unit tests for new services plus integration checks using `test_workflow.py` when touching pipeline orchestration. Include realistic ND2/CSV fixtures in `data/` and clean up any temporary outputs created during tests.

## Commit & Pull Request Guidelines
Commits follow concise, present-tense summaries (e.g., `optimize image viewer`). Group related changes; avoid sweeping refactors alongside feature work. Before sending a PR, ensure lint, format, type check, and tests are green, and summarize changes plus manual validation performed. Link relevant issues and, for UI adjustments, attach before/after imagery or describe observable impact. Cross-reference architecture notes (e.g., `MVC.md`) when deviating from established patterns so reviewers can reason about the change.

## Qt MVC Architecture Notes
Controllers reside in `pyama_qt/controllers`, models in `.../models`, and views in `.../views`. Never dispatch Qt signals from models or controllers; use the worker pattern outlined in `MVC.md` to handle long-running jobs without blocking the UI. New contributors should mirror existing controller templates to keep the signal flow predictable.

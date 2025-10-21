# Repository Guidelines

## Documentation Synchronization

**IMPORTANT**: When updating this file (AGENTS.md) or CLAUDE.md, sync the changes to both files to
maintain consistency across the repository documentation.

## Project Structure & Module Organization

The workspace is managed by uv and contains two installable packages: `pyama-core` (processing logic under
`pyama-core/src/pyama_core`) and `pyama-qt` (Qt GUI under `pyama-qt/src/pyama_qt`). Shared integration tests live in
`tests/`, and sample assets sit in `data/`. Keep automation scripts, notebooks, and large outputs out of package `src/`
trees to preserve clean wheels.

### Result Artifacts

- Workflow execution writes `processing_results.yaml`, encoding `channels.pc` as `[phase_channel, [feature1, ...]]`,
  `channels.fl` as `[[channel, [feature1, ...]], ...]`, and a per-FOV `results` mapping.
- Each FOV now emits a single merged traces CSV (`*_traces.csv`) with feature columns suffixed by `_ch_{channel}`;
  downstream tools filter the combined file per channel. Legacy per-channel CSVs remain readable for backwards
  compatibility.

## Build, Test, and Development Commands

Run `uv sync --all-extras` to materialize dev tooling, then install both packages in editable mode via
`uv pip install -e pyama-core/` and `uv pip install -e pyama-qt/`. Launch the GUI with `uv run pyama-qt`. Core
validation commands: `uv run pytest` (full suite), `uv run python tests/test_workflow.py` (end-to-end pipeline smoke),
`uv run ruff check` / `uv run ruff format` (lint + formatting), and `uv run ty check` (static typing). Execute commands
from the repository root so workspace paths resolve.

## Coding Style & Naming Conventions

Python uses 4-space indentation, type hints, and snake_case for modules, packages, and functions (see
`pyama_core.processing.workflow.pipeline`). Prefer `pathlib.Path` for filesystem work and keep logging via module-level
loggers. Ruff enforces linting; resolve warnings rather than silencing them. When adding Qt code, follow the current
tab-based structure without strict MVC separation. Group code with structured comment separators:

- Major sections:
  `# ============================================================================= # SECTION NAME # =============================================================================`
- Subsections:
  `# ------------------------------------------------------------------------ # SUBSECTION # ------------------------------------------------------------------------`

### Import Organization

- **All import statements must be at the top of the file** - no scattered imports within functions
- Use absolute imports only - no relative imports (`.module` or `..parent.module`)

## Testing Guidelines

Target pytest-based tests under `tests/` or the relevant package mirror. Name files `test_*.py`, and structure fixtures
to reuse workflow contexts. Expand coverage with focused unit tests for new services plus integration checks using
`test_workflow.py` when touching pipeline orchestration. Include realistic ND2/CSV fixtures in `data/` and clean up any
temporary outputs created during tests.

## Commit & Pull Request Guidelines

Commits follow concise, present-tense summaries (e.g., `optimize image viewer`). Group related changes; avoid sweeping
refactors alongside feature work. Before sending a PR, ensure lint, format, type check, and tests are green, and
summarize changes plus manual validation performed. Link relevant issues and, for UI adjustments, attach before/after
imagery or describe observable impact. Cross-reference architecture notes (e.g., `MVC.md`) when deviating from
established patterns so reviewers can reason about the change.

## Qt Application Architecture Notes

The Qt GUI uses a simplified tab-based structure without strict MVC separation. Components are organized by
functionality in `pyama_qt/processing/`, `pyama_qt/analysis/`, and `pyama_qt/visualization/`. Use background workers (
`pyama_qt.services.threading`) for long-running tasks to avoid blocking the UI.

**Component Classes:**

- **ParameterTable** (`pyama_qt.components.parameter_table`): Table-based parameter editing widget (renamed from
  ParameterPanel)
- **ParameterPanel** (`pyama_qt.analysis.parameter`): Parameter visualization and analysis widget

### Qt Signal/Slot Guidelines

- All signal receiver methods must use `@Slot()` decorator for performance and type safety
- Use `_build_ui()` and `_connect_signals()` methods for Qt widget initialization
- Signal naming follows snake_case convention
- **Semantic signals only**: Child panels should emit semantic signals like `workflow_finished(success, message)`
  instead of generic `status_message(text)`
- **No redundant status messages**: Don't emit generic status messages when semantic signals already convey the same
  information
- **Event-specific signals**: Each major operation should have its own started/finished signal pair with rich data
  payload

#### Unified Signal Pattern

**IMPORTANT**: All operations across tabs must follow a consistent signal pattern for status updates:

**Required Signal Pattern:**

- `operation_started()` - Emitted when operation begins
- `operation_finished(bool, str)` - Emitted when operation completes (success, detailed_message)

**Status Message Guidelines:**

- **Success**: Show the detailed message from the operation (e.g., "Results saved to /path/to/output", "Samples loaded from /path/to/file")
- **Failure**: Show "Failed to [operation]: [error message]"
- **Started**: Show generic progress message (e.g., "Processing workflow started...", "Loading samples...")

**Examples:**

```python
# Processing Tab
workflow_started = Signal()
workflow_finished = Signal(bool, str)
microscopy_loading_started = Signal()
microscopy_loading_finished = Signal(bool, str)

# Merge Panel
merge_started = Signal()
merge_finished = Signal(bool, str)
samples_loading_started = Signal()
samples_loading_finished = Signal(bool, str)
samples_saving_started = Signal()
samples_saving_finished = Signal(bool, str)
```

**Handler Pattern:**

```python
@Slot(bool, str)
def _on_operation_finished(self, success: bool, message: str) -> None:
    """Handle operation finished event."""
    logger.info("Operation finished (success=%s): %s", success, message)
    if self._status_manager:
        if success:
            self._status_manager.show_message(message)  # Show detailed message
        else:
            self._status_manager.show_message(f"Failed to [operation]: {message}")
```

### One-Way UI→Model Binding Architecture

**IMPORTANT**: PyAMA-QT uses strict one-way binding from UI to model only. This prevents circular dependencies and makes
data flow predictable.

#### Requirements

- **UI→Model only**: User input updates model state, but models don't automatically update UI
- **No model→UI synchronization**: UI refreshes must be explicit, not automatic
- **Signal-based communication**: Cross-panel updates via explicit Qt signals
- **Manual mode pattern**: Parameter panels only update model when user enables manual editing
- **Direct assignment**: UI event handlers directly update model attributes

#### Implementation Pattern

```python
@Slot()
def _on_ui_widget_changed(self) -> None:
    """Handle UI widget change (UI→Model only)."""
    # Get value from UI widget
    ui_value = self._ui_widget.current_value()

    # Update model directly (one-way binding)
    self._model_attribute = ui_value

    # Optionally emit signal for other panels
    self.model_changed.emit()
```

#### Forbidden Patterns

- Automatic UI updates when model changes
- Bidirectional data binding
- Signal loops where UI changes trigger model changes which trigger UI changes
- Model→UI automatic synchronization

#### Allowed Patterns

- Initial UI population from model defaults
- Manual UI refresh methods called explicitly
- Cross-panel communication via signals
- Background workers loading data into model

#### Reference Documentation

See `pyama-qt/UI_MODEL_BINDINGS.md` for detailed panel-by-panel analysis and examples.

## Workflow Execution Philosophy

### No Artificial Timeouts

**IMPORTANT**: The workflow execution does not use artificial timeouts. Processing continues until completion or manual user cancellation.

**Rationale**:

- Timeouts don't scale with dataset complexity (number of FOVs, frames, features)
- Users can manually cancel if processing takes too long
- Prevents premature failures on large datasets
- Simplifies debugging by removing timeout-related failures

**Implementation**:

- No timeout parameter in `as_completed(futures)` calls
- No `TimeoutError` handling in workflow execution
- Cleanup operations are commented out to preserve partial results for debugging
- Users control workflow termination through GUI cancellation

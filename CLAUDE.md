# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Documentation Synchronization

**IMPORTANT**: When updating this file (CLAUDE.md) or AGENTS.md, sync the changes to both files to maintain consistency across the repository documentation.

## Project Overview

PyAMA is a modular Python application for microscopy image analysis consisting of three main packages in a UV workspace:

- **pyama-core**: Core processing library with analysis, processing workflows, and I/O utilities
- **pyama-qt**: Qt-based GUI with tabs for Processing, Analysis, and Visualization
- **pyama-fastapi**: FastAPI service for PyAMA processing (mentioned in docs but not present in workspace)

## Development Commands

### Environment Setup

```bash
# Install all dependencies including dev tools
uv sync --all-extras

# Install in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-qt/
```

### Testing

```bash
# Run pytest (test discovery from workspace root)
uv run pytest

# Run specific test workflow
uv run python tests/test_workflow.py
```

### Code Quality

```bash
# Lint code with ruff (from pyama-qt dev dependencies)
uv run ruff check

# Format code
uv run ruff format

# Type checking (use ty from dev dependencies)
uv run ty check
```

### Running the Application

```bash
# Launch main GUI application
uv run pyama-qt

# Alternative: run directly
uv run python pyama-qt/src/pyama_qt/main.py
```

## Architecture

### Core Processing Pipeline

The application centers around a workflow pipeline (`pyama_core.processing.workflow.pipeline.run_complete_workflow`) that orchestrates microscopy image processing through these services:

1. **CopyingService**: Handles data loading and copying from ND2 files (runs sequentially per batch)
2. **SegmentationService**: Cell segmentation using LOG-STD approach
3. **CorrectionService**: Background correction for fluorescence channels
4. **TrackingService**: Cell tracking across time points using IoU
5. **ExtractionService**: Feature extraction and trace generation to CSV

The pipeline processes FOVs in batches using multithreading (`ThreadPoolExecutor`). Each batch is copied sequentially, then split across threads for parallel processing through steps 2-5. Worker contexts are merged back into the parent context after completion.

### Processing Context

The `ProcessingContext` dataclass (in `pyama_core.processing.workflow.services.types`) is the central data structure that flows through the pipeline, containing:

- Output directory paths
- Channel configurations (`Channels` dataclass with `pc` and `fl` fields)
- Per-FOV result artifacts (`results` dict mapping FOV index to `ResultsPerFOV`)
- Processing parameters and time units
- Results are serialized to `processing_results.yaml` and can be merged across multiple workflow runs

**Result schema highlights**

- `channels.pc` serializes as `[phase_channel, [feature1, ...]]` and `channels.fl` as `[[channel, [feature1, ...]], ...]`, capturing both channel IDs and the enabled feature sets.
- `results[fov_id].traces` points to a single merged CSV per FOV. Feature columns are suffixed with `_ch_{channel_id}` (e.g., `intensity_total_ch_1`, `area_ch_0`) so downstream tools can isolate per-channel data.
- Legacy YAML fields (`results_paths`, per-channel `traces_csv`) are still read, but new writes always emit the unified structure.

### Qt Application Structure

The Qt GUI uses a simplified tab-based architecture without strict MVC separation:

**Main Components:**

- **ProcessingTab** (`pyama_qt.processing.main_tab`): Data processing workflows and parameter tuning
- **AnalysisTab** (`pyama_qt.analysis.main_tab`): Analysis models and fitting (maturation, maturation-blocked, trivial models)
- **VisualizationTab** (`pyama_qt.visualization.main_tab`): Data visualization and plotting

**Component Classes:**

- **ParameterTable** (`pyama_qt.components.parameter_table`): Table-based parameter editing widget (renamed from ParameterPanel)
- **ParameterPanel** (`pyama_qt.analysis.parameter`): Parameter visualization and analysis widget

**Background Workers:** Long-running tasks (fitting, ND2 loading) use QObject workers in separate threads via `pyama_qt.services.threading`

### Qt Signal/Slot Guidelines

- All signal receiver methods must use `@Slot()` decorator for performance and type safety
- Use `_build_ui()` and `_connect_signals()` methods for Qt widget initialization
- Signal naming follows snake_case convention
- **Semantic signals only**: Child panels should emit semantic signals like `workflow_finished(success, message)` instead of generic `status_message(text)`
- **No redundant status messages**: Don't emit generic status messages when semantic signals already convey the same information
- **Event-specific signals**: Each major operation should have its own started/finished signal pair with rich data payload
- Main tab handles status updates centrally through semantic signal handlers

### One-Way UI→Model Binding Architecture

**IMPORTANT**: PyAMA-QT uses strict one-way binding from UI to model only. This prevents circular dependencies and makes data flow predictable.

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

### Key Data Types

- ND2 files are the primary input format for microscopy data
- Processing operates on FOVs (fields of view) with configurable batch sizes and worker counts
- Channel indexing distinguishes phase contrast (pc) from fluorescence (fl) channels
- Outputs include segmentation masks, corrected fluorescence, and extracted traces (CSV format)

## Development Notes

- Uses UV for dependency management with workspace configuration
- Built on Python 3.11+ with scientific computing stack (numpy, scipy, scikit-image, xarray)
- Qt GUI built with PySide6
- Processing pipeline supports multiprocessing with configurable worker counts
- Test workflow available in `tests/test_workflow.py` for CLI testing
- Typing style: prefer built-in generics (dict, list, tuple) and union types using '|' over typing.Dict, typing.List, typing.Tuple, typing.Union
- **Import organization**: All import statements must be at the top of the file - no scattered imports within functions

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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
uv run ty
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

The pipeline processes FOVs in batches using multiprocessing (`ProcessPoolExecutor` with spawn context). Each batch is copied sequentially, then split across workers for parallel processing through steps 2-5. Worker contexts are merged back into the parent context after completion.

### Processing Context
The `ProcessingContext` dataclass (in `pyama_core.processing.workflow.services.types`) is the central data structure that flows through the pipeline, containing:
- Output directory paths
- Channel configurations (`Channels` dataclass with `pc` and `fl` fields)
- Per-FOV numpy array paths (`results_paths` dict mapping FOV index to `ResultsPathsPerFOV`)
- Processing parameters and time units
- Results are serialized to `processing_results.yaml` and can be merged across multiple workflow runs

### Qt Application Structure (MVC Pattern)
The Qt application follows a strict MVC architecture with clear separation of concerns:

**Signal Flow:**
- View → Controller: Qt signals (user actions like button clicks)
- Controller → Model: Direct method calls to update state
- Model → Controller: Qt signals when state changes
- Controller → View: Direct method calls to update UI

**Component Responsibilities:**
- **Models** (`pyama_qt/models/`): Expose setters/getters, emit signals on state changes, never reference controllers/views
- **Views** (`pyama_qt/views/`): Define UI layout, emit signals for user intent, offer idempotent setters for controllers, never call models/controllers directly
- **Controllers** (`pyama_qt/controllers/`): Own view and model references, connect all signals in `__init__`, translate between view events and model updates

**Main Pages:**
- **ProcessingPage**: Data processing workflows and parameter tuning
- **AnalysisPage**: Analysis models and fitting (maturation, maturation-blocked, trivial models)
- **VisualizationPage**: Data visualization and plotting

**Background Workers:** Long-running tasks (fitting, ND2 loading) use QObject workers in separate threads, emitting signals that controllers consume

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

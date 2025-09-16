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
uv run pyama

# Alternative: run directly
uv run python pyama-qt/src/pyama_qt/main.py
```

## Architecture

### Core Processing Pipeline
The application centers around a workflow pipeline (`pyama_core.processing.workflow.pipeline`) that orchestrates microscopy image processing through these services:

1. **CopyingService**: Handles data loading and copying from ND2 files
2. **SegmentationService**: Cell segmentation using LOG-STD approach
3. **CorrectionService**: Background correction for fluorescence channels
4. **TrackingService**: Cell tracking across time points
5. **ExtractionService**: Feature extraction and trace generation

### Processing Context
The `ProcessingContext` TypedDict (in `pyama_core.processing.workflow.services.types`) is the central data structure that flows through the pipeline, containing:
- Output directory paths
- Channel configurations (phase contrast + fluorescence channels)
- Per-FOV numpy array paths
- Processing parameters

### Qt Application Structure
The main Qt app (`pyama_qt.main`) uses a tabbed interface with three main pages:
- **ProcessingPage**: Data processing workflows and parameter tuning
- **AnalysisPage**: Analysis models and fitting (maturation, maturation-blocked, trivial models)
- **VisualizationPage**: Data visualization and plotting

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
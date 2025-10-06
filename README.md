# PyAMA

PyAMA is a modular Python application for microscopy image analysis. It consists of a core library, a Qt-based graphical user interface, and a FastAPI-based web service.

## Packages

This repository is a workspace containing the following packages:

*   `pyama-core`: Core processing library for PyAMA with analysis, processing workflows, and I/O utilities.
*   `pyama-qt`: Qt-based GUI for PyAMA with a tabbed interface for Processing, Analysis, and Visualization.
*   `pyama-fastapi`: FastAPI service for PyAMA processing (planned - not yet in workspace).

## Quick Start

### Installation

```bash
# Install all dependencies
uv sync --all-extras

# Install packages in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-qt/
```

### Running the Application

```bash
# Launch the Qt GUI
uv run pyama-qt
```

### Development

```bash
# Run tests
uv run pytest

# Lint and format code
uv run ruff check
uv run ruff format

# Type checking
uv run ty
```

## Project Structure

```
pyama/
├── pyama-core/          # Core processing library
│   └── src/pyama_core/
│       ├── analysis/    # Analysis models and fitting
│       ├── io/          # I/O utilities (ND2, CSV, YAML)
│       └── processing/  # Workflow pipeline and services
└── pyama-qt/            # Qt-based GUI
    └── src/pyama_qt/
        ├── controllers/ # MVC controllers
        ├── models/      # Data models
        └── views/       # Qt UI components
```

## Processing Pipeline

PyAMA processes microscopy data through a multi-step pipeline:

1. **Copying**: Extract frames from ND2 files to NPY format
2. **Segmentation**: Cell segmentation using LOG-STD approach
3. **Correction**: Background correction for fluorescence channels
4. **Tracking**: Cell tracking across time points using IoU
5. **Extraction**: Feature extraction and trace generation to CSV

The pipeline processes FOVs (fields of view) in batches with configurable parallelism.
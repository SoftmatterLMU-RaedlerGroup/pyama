# PyAMA

PyAMA is a modular Python application for microscopy image analysis. It consists of a core library, a Qt-based graphical user interface, and a FastAPI-based web service.

## Packages

This repository is a workspace containing the following packages:

*   `pyama-core`: Core processing library for PyAMA with analysis, processing workflows, and I/O utilities.
*   `pyama-qt`: Qt-based GUI for PyAMA with a tabbed interface for Processing, Analysis, and Visualization.

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
uv run ty check
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

## Architecture Documentation

For detailed information about the Qt GUI architecture and data binding patterns, see:

- **[UI Model Bindings](pyama-qt/UI_MODEL_BINDINGS.md)** - Comprehensive analysis of UI→Model binding patterns and data models used across all panels
- **[CRUSH.md](CRUSH.md)** - Development commands and coding standards
- **[AGENTS.md](AGENTS.md)** - Repository guidelines for AI agents
- **[CLAUDE.md](CLAUDE.md)** - Specific guidance for Claude Code

## Quality Control and Filtering

PyAMA applies several quality control measures to ensure reliable results:

### Cell Tracking Quality Filters
- **IoU threshold**: Minimum Intersection over Union of 0.1 for cell matching between frames
- **Size constraints**: Optional minimum/maximum cell size filters for tracking validation
- **Trajectory length**: Cells must exist for at least 30 frames to be included in analysis

### Segmentation Quality Parameters
- **LOG-STD window**: 3x3 neighborhood for local standard deviation computation
- **Adaptive thresholding**: Automatically computed as mode + 3σ of intensity histogram
- **Morphological cleanup**: Size-7 structuring element with 3 iterations for mask refinement

### Edge Exclusion
- **Border filtering**: Cells within 10 pixels of image edges are automatically excluded
- **Center-based filtering**: Entire cell traces removed if centroid touches border in any frame

### Background Correction
- **Foreground expansion**: 10-pixel dilation for accurate foreground mask creation
- **Tile-based estimation**: 256x256 overlapping tiles for robust background computation

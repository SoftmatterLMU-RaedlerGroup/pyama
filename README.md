# PyAMA

PyAMA is a modular Python application for microscopy image analysis. It consists of a core processing library, Qt-based graphical user interfaces, and command-line tools for workflow configuration and data processing.

## Packages

This repository is a workspace containing the following packages:

- `pyama-core`: Core processing library for PyAMA with analysis, processing workflows, and I/O utilities.
- `pyama-pro`: Qt-based GUI for PyAMA with a tabbed interface for Processing, Analysis, and Visualization.
- `pyama-air`: Interactive CLI and GUI wizards for configuring PyAMA workflows, merges, and analysis.
- `pyama-backend`: FastAPI backend providing REST API endpoints for processing and analysis.
- `pyama-frontend`: Next.js frontend application for web-based microscopy file browsing and metadata loading.
- `pyama-acdc`: Cell-ACDC integration plugin for launching PyAMA workflows from within Cell-ACDC.

## Quick Start

### Installation

```bash
# Install all dependencies
uv sync --all-extras

# Install packages in development mode
uv pip install -e pyama-core/
uv pip install -e pyama-pro/
uv pip install -e pyama-air/
```

### Running the Application

```bash
# Launch the Qt GUI
uv run pyama-pro

# Or use the guided workflow helpers
pyama-air gui
pyama-air cli
```

### Development

```bash
# Run tests
uv run pytest

# Run visual algorithm testing script
uv run python tests/test_algo.py

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
│       ├── cli/         # Command-line interface
│       ├── io/          # I/O utilities (ND2, CSV, YAML)
│       ├── plugin/      # Plugin system (loader, scanner)
│       ├── processing/  # Workflow pipeline and services
│       ├── types/       # Type definitions
│       └── visualization/ # Visualization utilities
├── pyama-pro/           # Qt-based GUI
│   └── src/pyama_pro/
│       ├── analysis/    # Analysis tab (models, fitting, quality)
│       ├── components/  # Reusable UI components
│       ├── processing/  # Processing tab (workflow, merge)
│       ├── types/       # Type definitions
│       ├── utils/       # Utility functions
│       └── visualization/ # Visualization tab (image, trace)
├── pyama-air/           # Interactive CLI and GUI wizards
│   └── src/pyama_air/
│       ├── analysis/    # Analysis wizard
│       ├── components/  # UI components
│       ├── convert/     # Convert wizard
│       ├── merge/       # Merge wizard
│       ├── types/       # Type definitions
│       ├── utils/       # Utility functions
│       └── workflow/    # Workflow wizard
├── pyama-backend/       # FastAPI backend for web services
│   └── src/pyama_backend/
│       ├── api/         # REST API endpoints
│       ├── jobs/        # Job management
│       └── main.py      # Application entry point
├── pyama-frontend/      # Next.js frontend application
│   └── src/
│       ├── app/         # Next.js app directory
│       ├── components/  # React components
│       ├── lib/         # Utility libraries
│       └── types/       # TypeScript type definitions
└── pyama-acdc/          # Cell-ACDC integration plugin
    └── src/pyama_acdc/
        ├── resources/   # Icons and logos
        └── _run.py      # Integration entry point
```

## Processing Pipeline

PyAMA processes microscopy data through a multi-step pipeline:

1. **Copying**: Extract frames from ND2 files to NPY format
2. **Segmentation**: Cell segmentation using LOG-STD approach
3. **Correction**: Background correction for fluorescence channels
4. **Tracking**: Cell tracking across time points using IoU
5. **Extraction**: Feature extraction and trace generation to CSV

The pipeline processes FOVs (fields of view) in batches with configurable parallelism.

## Documentation

### Usage Guides

- **[pyama-pro/README.md](pyama-pro/README.md)** - Complete guide for using the PyAMA-Pro GUI
- **[pyama-air/README.md](pyama-air/README.md)** - Guide for using PyAMA-Air CLI and GUI wizards
- **[pyama-core/README.md](pyama-core/README.md)** - API documentation and examples for PyAMA-Core
- **[pyama-backend/README.md](pyama-backend/README.md)** - FastAPI backend documentation and API design
- **[pyama-frontend/README.md](pyama-frontend/README.md)** - Next.js frontend application guide
- **[pyama-acdc/README.md](pyama-acdc/README.md)** - Cell-ACDC integration plugin documentation

### Architecture Documentation

For detailed information about the Qt GUI architecture and data binding patterns, see:

- **[AGENTS.md](AGENTS.md)** - Repository guidelines for AI agents and Claude Code
- **[pyama-core/WORKFLOW.md](pyama-core/WORKFLOW.md)** - Detailed processing workflow documentation
- **[pyama-backend/API.md](pyama-backend/API.md)** - REST API endpoint specifications

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

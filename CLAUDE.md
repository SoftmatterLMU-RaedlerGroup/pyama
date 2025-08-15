# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Development Commands

### Running the Applications

```bash
# Process microscopy data
uv run python -m pyama_qt process

# Visualize results
uv run python -m pyama_qt viz
```

### Development Workflow

```bash
# Install dependencies
uv sync

# Install with dev dependencies
uv sync --all-extras

# Run linting
uv run ruff check src/

# Fix linting issues
uv run ruff check --fix src/

# Format code (ruff formatter)
uv run ruff format src/
```

### Testing

```bash
# Run tests (pytest and pytest-qt are in dev dependency group)
uv run python -m pytest tests/

# Install additional test dependencies if needed
uv add --group dev pytest pytest-qt
```

## High-Level Architecture

### Core System Design

PyAMA-Qt is a dual-GUI microscopy analysis suite with a clear separation between processing and visualization:

1. **Processing Pipeline**: ND2 → Extract → Binarize → Correct → Track → CSV
2. **Parallel Architecture**: Sequential extraction followed by parallel FOV processing using process pools
3. **Memory Strategy**: Memory-mapped arrays and batch processing for handling large datasets

### Key Architectural Patterns

#### Service/Utils Separation

- **Services** (`/services/`): Handle I/O, orchestration, and Qt integration
- **Utils** (`/utils/`): Pure computational algorithms without side effects
- **Core** (`/core/`): Shared data structures and utilities

#### Qt Threading Model

All long-running operations use worker threads to maintain responsive UI:

```python
# Worker moves to thread, signals communicate results
worker.moveToThread(thread)
worker.finished.connect(handler)
```

#### Process-Based Parallelism

The workflow uses ProcessPoolExecutor to bypass Python's GIL:

- Stage 1: Sequential ND2 extraction (avoids file contention)
- Stage 2-4: Parallel processing per FOV batch

### Critical Implementation Details

#### Multiprocessing Configuration

Both applications require specific multiprocessing setup for Windows compatibility:

```python
import multiprocessing as mp

if __name__ == "__main__":
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    main()
```

#### PySide6 Signals (NOT PyQt)

```python
from PySide6.QtCore import Signal  # Correct
# NOT: from PyQt6.QtCore import pyqtSignal
```

#### Type Hints (Python 3.11+ style)

```python
def process(data: list[str]) -> dict[str, object]:  # Correct
# NOT: from typing import List, Dict

# Use typing_extensions for advanced types when needed
from typing_extensions import TypedDict
```

#### File Naming Convention

Pattern: `{base_name}_fov{index:04d}_{suffix}.{ext}`

- Always use 4-digit FOV indices (0000-9999)

#### Data Flow

```
ND2 File → Batch Extraction → NPY Files → Worker Pool → Results
           (Sequential)      (Memory-mapped)  (Parallel)
```

### Algorithm Implementations

#### Binarization (Logarithmic Standard Deviation)

- Location: `processing/utils/binarization.py`
- Numba-optimized for phase contrast microscopy
- Default mask_size: 3

#### Background Correction (Schwarzfischer)

- Location: `processing/utils/background_correction.py`
- Grid-based background estimation
- Default grid: 7x5 divisions

#### Cell Tracking

- Location: `processing/utils/tracking.py`
- Overlap-based frame-to-frame tracking
- Maintains consistent cell IDs across time series

### Project Output Structure

```
output_dir/
├── fov_0000/
│   ├── *_phase_contrast_raw.npy
│   ├── *_fluorescence_raw.npy
│   ├── *_binarized.npz
│   ├── *_fluorescence_corrected.npz
│   └── *_traces.csv
├── fov_0001/
│   └── ... (same structure)
```

### Core Type Definitions

The project uses TypedDict classes for structured data:

- `ND2Metadata`: Essential ND2 file metadata (location: `core/data_loading.py`)
- `ProcessingResults`: Processing pipeline results structure

### Performance Considerations

1. **Memory Management**: Uses memory-mapped arrays to handle datasets larger than RAM
2. **Batch Processing**: Configurable batch_size (default: 10 FOVs) to balance memory and performance
3. **Numba JIT**: Critical loops compiled for near-C performance
4. **Sparse Storage**: Binary masks stored as sparse arrays to save space

### Common Parameters

- `mask_size`: 3 (binarization window)
- `div_horiz`: 7 (background correction horizontal divisions)
- `div_vert`: 5 (background correction vertical divisions)
- `min_trace_length`: 20 (minimum frames for valid trace)
- `batch_size`: 10 (FOVs per processing batch)

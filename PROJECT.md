# PyAMA-Qt Project Overview

## Core Concepts

### 1. Two-Application Architecture

PyAMA-Qt consists of two standalone GUI applications:

- **Processing Application** (`python -m pyama_qt process`): Handles ND2 file processing through a multi-stage pipeline
- **Visualization Application** (`python -m pyama_qt viz`): Interactive visualization of processed results

### 2. Processing Pipeline

The processing pipeline follows a strict sequence:

```
ND2 File → Extract → Binarize → Correct Background → Track & Extract → CSV Output
```

#### Stage 1: Extraction (Sequential)

- Extracts frames from ND2 files to NPY format
- Sequential processing to avoid ND2 file contention
- Outputs: `phase_contrast_raw.npy`, `fluorescence_raw.npy`

#### Stage 2: Parallel Processing

- **Binarization**: Logarithmic standard deviation method for phase contrast
- **Background Correction**: Schwarzfischer algorithm for fluorescence
- **Trace Extraction**: Cell tracking and feature extraction
- Process-based parallelism (bypasses Python GIL)

### 3. Data Flow Architecture

```
ND2 → Batch Extractor → NPY Files → Worker Pool → Results
           ↓                ↓            ↓
      Sequential      Memory-mapped   Parallel
      Extraction         Arrays       Processing
```

Key data types:
- **ND2Metadata**: Essential metadata from ND2 files (dimensions, channels, pixel size)
- **ProcessingResults**: Catalog of all processed data paths organized by FOV
- **ExtractionContext**: Context for cell feature extraction algorithms
- **FeatureData/PositionData**: Parsed trace data structures for visualization

### 4. Memory Management Strategy

- **Memory-mapped arrays**: Large datasets accessed without loading into RAM
- **Batch processing**: Extract and process FOVs in configurable batches
- **Optional cleanup**: Delete raw NPY files after successful processing
- **Lazy loading**: Visualization loads data on-demand

### 5. File Organization

```
output_dir/
├── fov_0000/
│   ├── *_phase_contrast_raw.npy        # Stage 1 output
│   ├── *_fluorescence_raw.npy          # Stage 1 output
│   ├── *_binarized.npz                 # Stage 2 output
│   ├── *_fluorescence_corrected.npz    # Stage 2 output
│   ├── *_traces.csv                    # Final output
│   └── pyama_project.toml              # Project metadata
├── fov_0001/
│   └── ...
```

### 6. Service Architecture Pattern

- **Services** (`/services/`): Handle I/O operations and orchestration
- **Utils** (`/utils/`): Pure algorithms without I/O dependencies
- **Core** (`/core/`): Shared modules between processing and visualization apps
- Clear separation between business logic and infrastructure

### 7. Qt Threading Model

```python
# Worker-thread pattern for long-running operations
class Worker(QObject):
    finished = Signal(bool, str)

    def run_processing(self):
        # Perform work in background thread
        self.finished.emit(success, message)

# Main thread creates worker and thread
self.thread = QThread()
self.worker = Worker()
self.worker.moveToThread(self.thread)
```

### 8. Signal System

Visual feedback through color-coded status indicators:

- **Gray**: Pending/waiting
- **Orange**: Currently processing
- **Green**: Completed successfully
- **Red**: Failed/error

### 9. Error Handling Philosophy

- **Non-blocking**: Errors reported via Qt signals
- **Graceful degradation**: Continue processing other FOVs on failure
- **Detailed logging**: File-based logging with queue handlers
- **User feedback**: Real-time status updates in GUI

### 10. Performance Optimizations

- **Numba JIT**: Critical algorithms compiled for near-C performance
- **Process pools**: True parallelism for CPU-intensive operations
- **Batch I/O**: Minimize file system operations
- **Sparse data structures**: Efficient storage of binary masks
- **nd2 library**: Modern Python bindings for efficient ND2 file access

## Project Structure

### Directory Layout

```
src/pyama_qt/
├── core/                           # Shared utilities
│   ├── data_loading.py            # ND2 loading, result discovery
│   ├── cell_feature.py            # Feature extraction definitions
│   └── logging_config.py          # Logging configuration
├── processing/                     # Processing application
│   ├── main.py                    # Processing GUI main
│   ├── services/                  # Processing services
│   │   ├── base.py               # Base service classes
│   │   ├── copy.py               # ND2 to NPY extraction
│   │   ├── binarization.py       # Phase contrast binarization
│   │   ├── background_correction.py  # Fluorescence correction
│   │   ├── trace_extraction.py   # Cell tracking & extraction
│   │   └── workflow.py           # FOV-by-FOV coordination
│   ├── utils/                     # Core algorithms (no I/O)
│   │   ├── binarization.py       # Log-std algorithm
│   │   ├── background_correction.py  # Schwarzfischer algorithm
│   │   ├── tracking.py           # Cell ID assignment
│   │   ├── copy.py               # Copy utilities
│   │   └── traces.py             # Trace calculation & feature extraction
│   └── ui/                        # Processing UI
│       ├── main_window.py
│       └── widgets/
│           ├── logger.py
│           └── workflow.py
└── visualization/                  # Visualization application
    ├── main.py                    # Visualization GUI main
    ├── utils/                     # Visualization utilities
    │   └── trace_parser.py        # CSV trace data parsing
    └── ui/                        # Visualization UI
        ├── main_window.py
        └── widgets/
            ├── project_loader.py
            ├── trace_viewer.py
            ├── image_viewer.py
            └── preprocessing_worker.py
```

## Coding Standards

### Package Management

- Use **uv** for dependency management (`uv run`, `uv add`)
- Project built with **PySide6** (Qt for Python)

### PySide6 Signals

```python
# CORRECT - PySide6
from PySide6.QtCore import Signal

class MyWidget(QObject):
    my_signal = Signal(int)

# INCORRECT - PyQt syntax
# my_signal = pyqtSignal(int)  # Don't use this
```

### Python Type Annotations (Python 3.9+)

```python
# PREFERRED - Built-in types
def process_data(items: list[str]) -> dict[str, object]:
    pass

def get_user(user_id: int) -> User | None:
    pass

# AVOID - Legacy typing imports
from typing import Dict, List, Optional  # Don't import these
```

**Type Guidelines:**

- `dict` instead of `Dict`
- `list` instead of `List`
- `| None` instead of `Optional[]`
- `object` instead of `Any`
- `str | int` instead of `Union[str, int]`

**Still use `typing` for:**

- `TypedDict`, `Protocol`, `Callable`, `Generic`, `TypeVar`, `Literal`

### File Naming Convention

- Pattern: `{base_name}_fov{index:04d}_{suffix}.npz`
- 4-digit FOV indices (supports up to 10,000 FOVs)

### Default Processing Parameters

- `mask_size`: 3 (binarization window size)
- `div_horiz`: 7 (background correction grid)
- `div_vert`: 5 (background correction grid)
- `min_trace_length`: 3 (minimum frames for valid trace)

## Key Design Principles

1. **Separation of Concerns**: Utils contain algorithms, Services handle I/O, Core shares fundamentals
2. **Memory Efficiency**: Uses memory-mapped arrays for large datasets
3. **Consistent Naming**: 4-digit FOV indices throughout
4. **True Parallelism**: Process-based workers bypass GIL
5. **Fault Tolerance**: Can resume from last completed batch
6. **Non-blocking UI**: All heavy operations in background threads
7. **Progressive Loading**: Visualization preloads adjacent FOVs
8. **Modular Architecture**: Services and utils can be tested independently
9. **Feature Extensibility**: Cell features centralized in core module for easy extension

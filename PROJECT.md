# PyAMA-Qt Project Overview

## Project Structure

### Directory Layout

```
src/pyama_qt/
├── core/                           # Shared utilities
│   ├── __init__.py
│   └── data_loading.py            # ND2 loading, result discovery
├── processing/                     # Processing application
│   ├── __init__.py
│   ├── main.py                    # Processing GUI main
│   ├── services/                  # Processing services
│   │   ├── base.py               # Base service classes
│   │   ├── binarization.py       # Phase contrast binarization
│   │   ├── background_correction.py  # Fluorescence correction
│   │   ├── trace_extraction.py   # Cell tracking & extraction
│   │   └── workflow.py           # FOV-by-FOV coordination
│   ├── utils/                     # Core algorithms (no I/O)
│   │   ├── binarization.py       # Log-std, otsu algorithms
│   │   ├── background_correction.py  # Schwarzfischer algorithm
│   │   ├── tracking.py           # Cell ID assignment
│   │   ├── extraction.py         # Feature extraction
│   │   └── traces.py             # Trace calculation
│   └── ui/                        # Processing UI
│       ├── main_window.py
│       └── widgets/
│           ├── fileloader.py
│           ├── logger.py
│           └── workflow.py
└── visualization/                  # Visualization application
    ├── __init__.py
    ├── main.py                    # Visualization GUI main
    └── ui/                        # Visualization UI
        ├── main_window.py
        └── widgets/
            ├── project_loader.py
            ├── trace_viewer.py
            └── image_viewer.py
```

### Parallel Processing Architecture

```
ND2 File → [Batch Extractor] → NPY Files → [Worker Pool] → Results
                                    ↓              ↓
                              fov_0000.npy    Worker 0
                              fov_0001.npy    Worker 1
                              fov_0002.npy    Worker 2
                              fov_0003.npy    Worker 3
```

### Output Structure Per FOV

```
output_dir/
├── fov_0000/
│   ├── 250129_HuH7_fov0000_phase_contrast_raw.npy      # Stage 1: Extracted
│   ├── 250129_HuH7_fov0000_fluorescence_raw.npy        # Stage 1: Extracted
│   ├── 250129_HuH7_fov0000_binarized.npz              # Stage 2: Processed
│   ├── 250129_HuH7_fov0000_fluorescence_corrected.npz  # Stage 2: Processed
│   ├── 250129_HuH7_fov0000_traces.csv                  # Stage 2: Processed
│   └── pyama_project.toml                               # Project metadata
```

### Entry Points

- **`python -m pyama_qt process`**: Processing application (GUI)
- **`python -m pyama_qt viz`**: Visualization application (GUI)

## Coding Preferences

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
from typing import Dict, List, Optional, Any  # Don't import these

def process_data(items: List[str]) -> Dict[str, Any]:  # Don't do this
    pass
```

**Type Guidelines:**

- `dict` instead of `Dict`
- `list` instead of `List`
- `tuple` instead of `Tuple`
- `set` instead of `Set`
- `| None` instead of `Optional[]`
- `object` instead of `Any`
- `str | int` instead of `Union[str, int]`

**Still use `typing` for:**

- `TypedDict`, `Protocol`, `Callable`, `Generic`, `TypeVar`, `Literal`

### QThread Pattern

```python
# Worker-thread pattern
class Worker(QObject):
    finished = Signal(bool, str)  # success, message

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run_processing(self):
        try:
            # Do work
            self.finished.emit(True, "Success")
        except Exception as e:
            self.finished.emit(False, str(e))

# In main window
def start_background_work(self, params):
    self.thread = QThread()
    self.worker = Worker(params)
    self.worker.moveToThread(self.thread)

    # Connect signals
    self.thread.started.connect(self.worker.run_processing)
    self.worker.finished.connect(self.thread.quit)
    self.worker.finished.connect(self.worker.deleteLater)
    self.thread.finished.connect(self.thread.deleteLater)

    self.thread.start()
```

### File Naming Convention

- Pattern: `{base_name}_fov{index:04d}_{suffix}.npz`
- 4-digit FOV indices (supports up to 10,000 FOVs)

### Memory Management

- Use memory-mapped arrays for large datasets
- Pattern: `np.memmap(output_path, dtype=dtype, mode="w+", shape=shape)`
- Extract only needed data for current batch
- Option to delete raw NPY files after processing

### Service Design Pattern

- **Services**: Handle I/O and orchestration
- **Utils**: Pure algorithms without I/O dependencies
- Services registered in dependency order
- Chain: Binarization → Background Correction → Trace Extraction

### Signal Light System

- **Gray**: Pending/waiting
- **Orange**: Currently processing
- **Green**: Completed successfully
- **Red**: Failed/error

### Error Handling

- Signals: `error_occurred`, `status_updated`, `step_completed`
- Async signal-based error reporting
- File logging with queue-based, non-blocking I/O

### Default Processing Parameters

- `mask_size`: 3
- `div_horiz`: 7
- `div_vert`: 5
- `min_trace_length`: 3

### Key Design Principles

1. **Separation of Concerns**: Utils contain algorithms, Services handle I/O
2. **Memory Efficiency**: Uses memory-mapped arrays for large datasets
3. **Consistent Naming**: 4-digit FOV indices
4. **True Parallelism**: Process-based workers bypass GIL
5. **Fault Tolerance**: Can resume from last completed batch

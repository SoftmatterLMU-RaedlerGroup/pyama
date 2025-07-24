# PyAMA-Qt Development Notes

## Project Setup

This project uses **uv** for dependency management and **PySide6** for the GUI framework.

- Use `uv run` to execute commands in the project environment
- Use `uv add <package>` to add new dependencies
- The project is built with PySide6 (Qt for Python)

## PySide6 Signal Usage

When using PySide6, signals should be defined using `Signal` instead of `pyqtSignal`:

```python
from PySide6.QtCore import Signal

class MyWidget(QObject):
    # Correct - PySide6 syntax
    my_signal = Signal(int)
    
    # Incorrect - PyQt syntax
    # my_signal = pyqtSignal(int)  # This will cause import errors
```

**Important:** PySide6 uses `Signal` while PyQt uses `pyqtSignal`. Since this project uses PySide6, always use `Signal` for signal definitions.

## QThread Usage Pattern

For background processing, use the worker-thread pattern instead of moving existing objects to threads:

```python
from PySide6.QtCore import QThread, QObject, Signal

class Worker(QObject):
    """Worker class for background processing."""
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, params):
        super().__init__()
        self.params = params
    
    def run_processing(self):
        """Main processing method."""
        try:
            # Do processing work here
            success = True
            self.finished.emit(success, "Processing completed")
        except Exception as e:
            self.finished.emit(False, f"Error: {str(e)}")

# In main window:
def start_background_work(self, params):
    # Create thread and worker
    self.thread = QThread()
    self.worker = Worker(params)
    
    # Move worker to thread
    self.worker.moveToThread(self.thread)
    
    # Connect signals
    self.thread.started.connect(self.worker.run_processing)
    self.worker.finished.connect(self.thread.quit)
    self.worker.finished.connect(self.worker.deleteLater)
    self.thread.finished.connect(self.thread.deleteLater)
    
    # Start processing
    self.thread.start()
```

**Avoid:** Moving existing objects with complex signal connections to threads using `moveToThread()`.

## Python Type Annotations

**Use built-in types instead of typing module imports whenever possible (Python 3.9+):**

### Preferred (Modern):
```python
# Use built-in generic types
def process_data(items: list[str]) -> dict[str, object]:
    pass

def get_user(user_id: int) -> User | None:
    pass

def handle_response(data: dict[str, object]) -> None:
    pass
```

### Avoid (Legacy):
```python
# Don't import from typing when built-ins work
from typing import Dict, List, Optional, Any

def process_data(items: List[str]) -> Dict[str, Any]:
    pass

def get_user(user_id: int) -> Optional[User]:
    pass
```

### Type Annotation Guidelines:
- **`dict`** instead of `Dict`
- **`list`** instead of `List`
- **`tuple`** instead of `Tuple`
- **`set`** instead of `Set`
- **`| None`** instead of `Optional[]`
- **`object`** instead of `Any` (be more specific when possible)
- **`str | int`** instead of `Union[str, int]`

### When to still use `typing`:
- `TypedDict` for structured dictionaries (or `typing_extensions.TypedDict`)
- `Protocol` for structural typing
- `Callable` for function types
- `Generic` and `TypeVar` for generic classes
- `Literal` for literal types

### Example Conversion:
```python
# Before
from typing import Dict, List, Optional, Any
def process_workflow(data_info: Dict[str, Any], params: Optional[Dict[str, Any]] = None) -> List[str]:
    pass

# After  
def process_workflow(data_info: dict[str, object], params: dict[str, object] | None = None) -> list[str]:
    pass
```

## Project Structure and Dual-App Architecture

This project now supports both **processing** and **visualization** applications in a unified codebase:

### Entry Points
- **`pyama-process`**: Processing application (GUI)
- **`pyama-viz`**: Visualization application (GUI)  
- **`python -m pyama_qt process`**: Processing application
- **`python -m pyama_qt viz`**: Visualization application
- **`pyama-qt`**: Legacy entry point (defaults to processing)

### Directory Structure
```
src/pyama_qt/
├── core/                           # Shared utilities
│   ├── __init__.py
│   └── data_loading.py            # ND2 loading, result discovery
├── processing/                     # Processing application
│   ├── __init__.py
│   ├── main.py                    # Processing GUI main
│   ├── cli.py                     # Processing CLI
│   ├── services/                  # Processing services
│   ├── utils/                     # Processing algorithms  
│   └── ui/                        # Processing UI
└── visualization/                  # Visualization application
    ├── __init__.py
    ├── main.py                    # Visualization GUI main
    └── ui/                        # Visualization UI components
        ├── main_window.py
        └── widgets/
            ├── project_loader.py
            ├── trace_viewer.py
            └── image_viewer.py
```

### Processing Application (`src/pyama_qt/processing/`)

#### Services (`processing/services/`)
- **`base.py`**: Base classes for all processing services, provides common utilities
- **`binarization.py`**: Phase contrast image binarization service 
- **`background_correction.py`**: Fluorescence background correction service
- **`trace_extraction.py`**: Cell tracking and feature extraction service
- **`workflow.py`**: Coordinates execution of all processing steps FOV-by-FOV

#### Utils (`processing/utils/`)
Core algorithms without I/O dependencies:
- **`binarization.py`**: Binarization algorithms (logarithmic std, otsu, etc.)
- **`background_correction.py`**: Schwarzfischer background correction algorithm
- **`tracking.py`**: Cell tracking algorithms for assigning consistent IDs
- **`extraction.py`**: Feature extraction from labeled cell regions
- **`traces.py`**: High-level trace calculation combining tracking + extraction

#### CLI Interface
- **`processing/cli.py`**: Command-line interface for headless processing

### Visualization Application (`src/pyama_qt/visualization/`)

#### Main Components
- **`main.py`**: Visualization application entry point
- **`ui/main_window.py`**: Main visualization window with tabbed interface

#### UI Widgets (`visualization/ui/widgets/`)
- **`project_loader.py`**: Load and browse processing results
- **`trace_viewer.py`**: Interactive trace plotting and analysis (requires matplotlib)
- **`image_viewer.py`**: Display microscopy images and processing results

### Core Utilities (`src/pyama_qt/core/`)
Shared functionality between both applications:
- **`data_loading.py`**: 
  - `load_nd2_metadata()`: Load ND2 file metadata
  - `discover_processing_results()`: Find and catalog processing outputs
  - `load_traces_csv()`: Load cellular trace data
  - `load_image_data()`: Load NPZ image arrays

## Installation and Usage

### Installation
```bash
# Basic installation (processing only)
uv add pyama-qt

# With visualization support
uv add "pyama-qt[viz]"  # Includes matplotlib

# Development installation
uv add "pyama-qt[dev,viz]"
```

### Usage Examples

#### Processing Application
```bash
# Launch processing GUI
pyama-process
# or
python -m pyama_qt process

# Command-line processing
python -m pyama_qt.processing.cli input.nd2 -o results/
```

#### Visualization Application
```bash
# Launch visualization GUI
pyama-viz
# or  
python -m pyama_qt viz

# Then use File > Open Project to load processing results directory
```

#### Workflow Integration
1. **Process data**: Use `pyama-process` to analyze ND2 files
   - Creates organized output directories with FOV subdirectories
   - Generates `pyama_project.toml` file with complete processing metadata
2. **Visualize results**: Use `pyama-viz` to open the processing results directory
   - Automatically detects and reads project files for enhanced functionality
   - Falls back to file pattern discovery for legacy projects
3. **Interactive analysis**: View traces, images, and export data with full context

## Project File System (TOML)

### Project File Creation
Processing runs automatically create `pyama_project.toml` files containing:

```toml
[project]
name = "experiment_001"
created = "2024-01-15T14:30:00Z"
pyama_version = "0.1.0"
description = "Cell growth analysis experiment"

[input]
nd2_file = "/path/to/data.nd2"
filename = "data.nd2"
channels = ["Phase Contrast", "GFP"] 
pc_channel = 0
fl_channel = 1

[processing]
status = "completed"
started = "2024-01-15T14:30:00Z"
completed = "2024-01-15T15:45:00Z"
duration_seconds = 4500

[processing.parameters]
mask_size = 3
div_horiz = 7
div_vert = 5
min_trace_length = 3

[output]
directory = "/path/to/results"
fov_count = 4

[output.fov_0000]
binarized = "data_fov0000_binarized.npz"
phase_contrast = "data_fov0000_phase_contrast.npz"
fluorescence_corrected = "data_fov0000_fluorescence_corrected.npz"
traces = "data_fov0000_traces.csv"
status = "completed"
```

### Visualization Benefits
Project files enable the visualization app to:
- **Show processing history**: Parameters used, timing, success/failure status
- **Validate data integrity**: Check if all referenced files exist
- **Display rich metadata**: Processing steps, duration, FOV status
- **Handle errors gracefully**: Meaningful error messages for missing files
- **Provide context**: Complete provenance of how data was processed

### Core Functions
- **`create_project_file()`**: Generate project file at processing start
- **`update_project_step_status()`**: Track individual processing steps
- **`update_project_fov_status()`**: Track FOV completion status
- **`finalize_project_file()`**: Complete project with final statistics
- **`load_project_file()`**: Read project metadata for visualization
- **`validate_project_files()`**: Check file integrity

### Processing Flow
```
ND2 File → Binarization → Background Correction → Trace Extraction → CSV Results
                                                                        ↓
                                                          Visualization App
```

Each FOV is processed completely through all steps before moving to the next FOV, with results organized in separate directories:
```
project_output/
├── fov_0000/
│   ├── filename_fov0000_binarized.npz
│   ├── filename_fov0000_phase_contrast.npz
│   ├── filename_fov0000_fluorescence_corrected.npz
│   └── filename_fov0000_traces.csv
├── fov_0001/
│   └── ...
```

### Key Design Principles
1. **Separation of Concerns**: Utils contain algorithms, Services handle I/O and orchestration
2. **Memory Efficiency**: Uses memory-mapped arrays for large datasets
3. **CLI/GUI Compatibility**: Services work with or without Qt parent
4. **Consistent Naming**: 4-digit FOV indices (supports up to 10,000 FOVs)

## UI Signal Light System

### Signal Light Colors
The workflow UI displays colored signal lights for each processing step:
- **Gray (#cccccc)**: Pending/waiting
- **Orange (#FFA500)**: Currently processing
- **Green (#4CAF50)**: Completed successfully  
- **Red (#F44336)**: Failed/error

### Signal Change Triggers
Signal colors change based on these events:

#### 1. Workflow Start
- **Location**: `src/pyama_qt/ui/main_window.py:190`
- **Method**: `start_workflow_processing()` → `workflow.reset_signal_lights()`
- **Effect**: Sets all lights to gray (pending)

#### 2. Step Completion
- **Location**: `src/pyama_qt/ui/main_window.py:206-211`
- **Method**: `on_step_completed(step_name)`
- **Trigger**: Services emit `step_completed` signal
- **Effect**: Maps service name to UI light, sets to green

#### 3. Step Name Mapping
- **Location**: `src/pyama_qt/ui/main_window.py:164-168`
- **Mapping**:
  ```python
  self.step_name_mapping = {
      'Binarization': 'segmentation',
      'Background Correction': 'background_correction',
      'Pickle Maximum Bounding Box': 'bounding_box'
  }
  ```
- **Note**: "Trace Extraction" service needs to be added to this mapping

#### 4. Signal Light Control
- **Location**: `src/pyama_qt/ui/widgets/workflow.py:179-198`
- **Method**: `set_signal_light_status(step, status)`
- **Usage**: Called from main window to update individual lights

### Adding New Processing Steps
To add a new step with signal light support:
1. Add service to `src/pyama_qt/services/workflow.py`
2. Add signal light in `src/pyama_qt/ui/widgets/workflow.py:setup_workflow_steps()`
3. Add mapping in `src/pyama_qt/ui/main_window.py:step_name_mapping`
4. Ensure service emits `step_completed` signal

## Key Processing Methods

### Core Service Methods
Each processing service follows the same pattern:

#### Binarization Service
- **Location**: `src/pyama_qt/services/binarization.py:25-118`
- **Method**: `BinarizationService.process_fov()`
- **Purpose**: Phase contrast binarization with memory-mapped output
- **Parameters**: `mask_size` (default: 3)
- **Outputs**: `binarized.npz`, `phase_contrast.npz`
- **Algorithm**: Uses `logarithmic_std_binarization()` from utils

#### Background Correction Service  
- **Location**: `src/pyama_qt/services/background_correction.py:25-131`
- **Method**: `BackgroundCorrectionService.process_fov()`
- **Purpose**: Schwarzfischer background correction on fluorescence
- **Dependencies**: Requires segmentation data from binarization
- **Parameters**: `div_horiz` (7), `div_vert` (5), `fl_channel`
- **Output**: `fluorescence_corrected.npz`

#### Trace Extraction Service
- **Location**: `src/pyama_qt/services/trace_extraction.py:25-103`
- **Method**: `TraceExtractionService.process_fov()`
- **Purpose**: Cell tracking and feature extraction
- **Dependencies**: Segmentation + corrected fluorescence data
- **Parameters**: `min_trace_length` (default: 3)
- **Output**: `traces.csv`

## File I/O and Data Loading

### ND2 Metadata Loading
- **GUI**: `src/pyama_qt/ui/widgets/fileloader.py:48-88`
  - **Method**: `ND2LoaderThread.run()`
  - **Purpose**: Background thread for metadata extraction
  - **Returns**: `ND2Metadata` TypedDict with channels, dimensions, frames

- **CLI**: `src/pyama_qt/cli.py:46-89` 
  - **Method**: `load_nd2_metadata()`
  - **Purpose**: Headless metadata loading with channel auto-detection
  - **Fallback**: Assigns channels when auto-detection fails

### Memory-Mapped Arrays
- **Location**: `src/pyama_qt/services/base.py:120-134`
- **Method**: `BaseProcessingService.create_memmap_array()`
- **Pattern**: `np.memmap(output_path, dtype=dtype, mode="w+", shape=shape)`
- **Usage**: Consistent across all services for large file handling

### File Naming Convention
- **Location**: `src/pyama_qt/services/base.py:160-172`
- **Method**: `BaseProcessingService.get_output_filename()`
- **Pattern**: `{base_name}_fov{index:04d}_{suffix}.npz`
- **Purpose**: Standardized naming across all services

## Threading and Background Processing

### Worker Thread Pattern
- **Location**: `src/pyama_qt/ui/main_window.py:13-40`
- **Class**: `WorkflowWorker`
- **Pattern**: Standard PySide6 worker with `moveToThread()`
- **Signals**: `finished = Signal(bool, str)` for completion

### Thread Management
- **Location**: `src/pyama_qt/ui/main_window.py:156-187`
- **Method**: `MainWindow.start_workflow_processing()`
- **Features**: Proper cleanup, signal connections, automatic deletion
- **Cancellation**: `_is_cancelled` flag in base service

## Error Handling and Logging

### Service Error Propagation
- **Location**: `src/pyama_qt/services/base.py:12-18`
- **Signals**: 
  - `error_occurred = Signal(str)` - Error messages
  - `status_updated = Signal(str)` - Progress updates  
  - `step_completed = Signal(str)` - Completion notifications
- **Pattern**: Async signal-based error reporting

### File Logging System
- **Location**: `src/pyama_qt/ui/widgets/logger.py:8-61`
- **Class**: `LogWriter` - Separate thread for non-blocking file I/O
- **Features**: Queue-based, mutex protection, automatic flushing
- **Activation**: `Logger.start_file_logging()` at lines 123-156

### CLI Logging
- **Location**: `src/pyama_qt/cli.py:21-43`
- **Method**: `setup_logging()`
- **Features**: Console + file logging, configurable levels
- **Format**: timestamp, logger name, level, message

## Parameter Handling

### Default Configuration
- **Location**: `src/pyama_qt/ui/widgets/workflow.py:238-283`
- **Method**: `Workflow.start_processing()`
- **Defaults**: mask_size=3, div_horiz=7, div_vert=5, min_trace_length=3
- **Usage**: Centralized parameter management

### CLI Parameters
- **Location**: `src/pyama_qt/cli.py:161-233`
- **Method**: `main()`
- **Features**: Complete argparse setup, validation, channel override
- **Usage**: `python pyama_cli.py data.nd2 -o results/ --mask-size 5`

## Common Patterns

### Service Registration
- **Location**: `src/pyama_qt/services/workflow.py:18-31`
- **Pattern**: Services registered in dependency order
- **Chain**: Binarization → Background Correction → Trace Extraction

### Data Info Structure
- **Standard Keys**: filepath, filename, pc_channel, fl_channel, metadata
- **Usage**: Passed through entire processing pipeline
- **Access**: Consistent dictionary access across all services

### Output Organization
- **Structure**: `output_dir/fov_{index:04d}/`
- **Files**: NPZ for arrays, CSV for traces
- **Naming**: Base name + FOV index + suffix pattern
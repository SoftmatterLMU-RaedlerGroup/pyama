# PyAMA-QT UI→Model Bindings Report

This document describes the UI→Model binding patterns and data models used across all panels in the PyAMA-QT application.

## Architecture Overview

PyAMA-QT follows a **one-way binding architecture** where user interactions in the UI update model attributes, but models don't automatically update the UI. This prevents circular dependencies and makes data flow predictable.

### Key Patterns:
- **UI→Model only**: User input updates model state
- **Signal-based communication**: Cross-panel updates via explicit signals
- **Manual mode**: Parameter panels only update when user enables manual editing
- **Background workers**: Heavy operations use threaded workers to avoid UI blocking

---

## Panel-by-Panel Analysis

### ProcessingConfigPanel (`processing/workflow.py`)

**Purpose**: Collect user inputs for running the processing workflow

**Models Held:**
```python
# File and directory paths
self._microscopy_path: Path | None = None
self._output_dir: Path | None = None

# Channel selections
self._phase_channel: int | None = None
self._fl_features: dict[int, list[str]] = {}
self._pc_features: list[str] = []

# Processing parameters
self._fov_start: int = 0
self._fov_end: int = 99
self._batch_size: int = 2
self._n_workers: int = 2

# Metadata
self._metadata: MicroscopyMetadata | None = None
```

**UI→Model Bindings:**
- File browsers → Path attributes
- Channel dropdowns → Channel selection attributes
- Parameter panel → Processing attributes (when manual mode enabled)
- Add/Remove buttons → Feature mapping dictionary

**Key Signals:**
- `microscopy_loading_started/finished`: File loading status
- `workflow_started/finished`: Processing lifecycle

---

### DataPanel (`analysis/data.py`)

**Purpose**: Load and manage analysis data for fitting

**Models Held:**
```python
# Analysis data
self._raw_data: pd.DataFrame | None = None
self._raw_csv_path: Path | None = None

# Model state
self._selected_cell: str | None = None
self._is_fitting: bool = False
self._model_type: str = "trivial"

# Model parameters
self._model_params: dict[str, float] = {}
self._model_bounds: dict[str, tuple[float, float]] = {}
```

**UI→Model Bindings:**
- CSV loader → DataFrame and path attributes
- Model selector → Model type and parameter defaults
- Parameter panel → Parameter values/bounds (when manual mode enabled)

**Key Signals:**
- `fitting_completed`: Results ready for other panels
- `status_message`: Progress updates

---

### FittingPanel (`analysis/fitting.py`)

**Purpose**: Display fitting results and individual cell fits

**Models Held:**
```python
# Display data
self._results_df: pd.DataFrame | None = None
self._raw_data: pd.DataFrame | None = None

# Selection state
self._selected_cell: str | None = None
```

**UI→Model Bindings:**
- Shuffle button → Emits request signal (no internal model update)
- Mostly display-only with external data updates via slots

**Key Signals:**
- `shuffle_requested`: Request random cell from DataPanel

---

### ResultsPanel (`analysis/results.py`)

**Purpose**: Visualize and analyze fitting results across all cells

**Models Held:**
```python
# Results data
self._results_df: pd.DataFrame | None = None

# UI selections
self._parameter_names: list[str] = []
self._selected_parameter: str | None = None
self._x_parameter: str | None = None
self._y_parameter: str | None = None
```

**UI→Model Bindings:**
- Parameter dropdowns → Selection attributes
- Filter checkbox → Triggers plot updates
- Direct one-way updates from UI to model

---

### ImagePanel (`visualization/image.py`)

**Purpose**: Display microscopy images and overlays for analysis

**Models Held:**
```python
# Image cache and display
self._image_cache: dict[str, np.ndarray] = {}
self._current_data_type: str = ""
self._current_frame_index = 0
self._max_frame_index = 0

# Trace data
self._trace_positions: dict[str, PositionData] = {}
self._active_trace_id: str | None = None
```

**UI→Model Bindings:**
- Channel selector → Current display type
- Frame controls → Frame index
- Canvas clicks → Trace selection and quality updates

**Key Signals:**
- `trace_selected`: User clicked on trace
- `trace_quality_toggled`: User right-clicked trace
- `frame_changed`: Frame navigation
- `visualization_requested`: Request data loading

---

### ProjectPanel (`visualization/project.py`)

**Purpose**: Load and manage project data from processing results

**Models Held:**
```python
# Project data
self._project_data: dict | None = None
```

**UI→Model Bindings:**
- Project loader → Project data dictionary
- FOV/channel selectors → Emits visualization requests
- One-way loading from disk to model

**Key Signals:**
- `project_loaded`: New project data available
- `visualization_requested`: Start visualization with selected parameters

---

### TracePanel (`visualization/trace.py`)

**Purpose**: Display and analyze individual trace data over time

**Models Held:**
```python
# Trace data
self._trace_features: dict[str, FeatureData] = {}
self._trace_positions: dict[str, PositionData] = {}
self._good_status: dict[str, bool] = {}

# Processing data
self._processing_df: pd.DataFrame | None = None

# UI state
self._active_trace_id: str | None = None
```

**UI→Model Bindings:**
- Feature dropdown → Plot selection
- Trace list → Active trace selection
- Quality toggle → Good status updates
- Pagination → Page navigation state

**Key Signals:**
- `trace_position_updated`: Position changes for image overlay
- `active_trace_changed`: New trace selection
- `frame_requested`: Request specific frame from ImagePanel

---

### ProcessingMergePanel (`processing/merge.py`)

**Purpose**: Merge multiple processing results into combined datasets

**Models Held:**
```python
# Table data
self._table: SampleTable | None = None

# Worker reference
self._merge_runner: WorkerHandle | None = None
```

**UI→Model Bindings:**
- Table widget → Direct table data updates
- File browsers → Path selections
- Buttons → Table management operations

**Key Signals:**
- `merge_completed`: Merge process finished
- `status_message`: Progress updates

---

## Data Model Types

### Common Model Types:
- **Path objects**: File and directory references
- **pandas DataFrames**: Tabular data (analysis results, processing data)
- **Dictionaries**: Structured data (trace features, project data)
- **Primitive types**: Parameters, indices, flags
- **Custom dataclasses**: Complex structures (PositionData, FeatureData)

### External Models:
- **MicroscopyMetadata**: From pyama-core.io
- **ChannelSelection/Channels**: From pyama-core processing types
- **ProcessingContext**: Workflow execution context

---

## Signal-Based Communication

Panels communicate via Qt signals rather than direct model sharing:

### Cross-Panel Signal Examples:
```python
# DataPanel → FittingPanel/ResultsPanel
fitting_completed.emit(results_df)

# ImagePanel ↔ TracePanel
trace_selected.emit(trace_id)
trace_position_updated.emit(trace_id, position_data)

# ProjectPanel → ImagePanel/TracePanel
visualization_requested.emit(project_data, fov_id, channels)
```

This maintains loose coupling between panels while enabling coordinated behavior.

---

## Best Practices

### For New Panels:
1. **Use one-way binding**: UI → model only
2. **Store minimal state**: Only what's needed for functionality
3. **Emit signals for cross-panel communication**
4. **Use background workers for heavy operations**
5. **Validate input before model updates**

### For Model Updates:
1. **Direct assignment in event handlers**: `self._model_attr = ui_value`
2. **Validation**: Check ranges, required fields, data types
3. **Signal emission**: Notify other components of changes
4. **Batch updates**: Group related changes together

### For UI Updates:
1. **Explicit refresh methods**: Don't bind model→UI automatically
2. **Slot-based updates**: Receive data via slots from other panels
3. **State synchronization**: Use explicit methods to sync UI with model

---

## File Structure

```
pyama-qt/src/pyama_qt/
├── analysis/
│   ├── data.py          # DataPanel - analysis data management
│   ├── fitting.py       # FittingPanel - individual cell fits
│   ├── main_tab.py      # AnalysisTab - coordinates analysis panels
│   └── results.py       # ResultsPanel - aggregate results visualization
├── components/
│   ├── mpl_canvas.py    # MplCanvas - matplotlib widget
│   └── parameter_panel.py # ParameterPanel - parameter input
├── processing/
│   ├── main_tab.py      # ProcessingTab - coordinates processing panels
│   ├── merge.py         # ProcessingMergePanel - merge operations
│   └── workflow.py      # ProcessingConfigPanel - workflow configuration
├── services/
│   └── threading.py     # Worker management utilities
├── types/
│   ├── analysis.py      # Analysis-related data structures
│   ├── processing.py    # Processing-related data structures
│   └── visualization.py # Visualization-related data structures
├── visualization/
│   ├── image.py         # ImagePanel - image display
│   ├── main_tab.py      # VisualizationTab - coordinates viz panels
│   ├── project.py       # ProjectPanel - project data loading
│   └── trace.py         # TracePanel - trace visualization
├── constants.py         # Application constants
├── main.py             # Application entry point
└── main_window.py      # Main application window
```

---

*This document provides a comprehensive overview of PyAMA-QT's UI→Model binding architecture. For implementation details, refer to the individual panel source files.*
# PyAMA-Qt Legacy Code Analysis

This document analyzes the legacy codebase in the `old/` directory, which contains two main components: the original PyAMA GUI application and a fluorescence fitting library.

## Directory Structure Overview

```
old/
├── pyama/                    # Main GUI application (tkinter-based)
│   ├── src/pyama/           # Core application source
│   ├── plugins/             # Plugin system
│   └── misc/                # Utility scripts
├── py_fit_fluorescence/     # Fluorescence curve fitting library
│   ├── models/              # Mathematical models
│   └── *.py                 # Fitting algorithms and utilities
├── MergeSingleFiles.ipynb   # Data merging utility notebook
└── PlotTraces.ipynb         # Trace visualization notebook
```

## PyAMA GUI Application (`old/pyama/`)

### Project Overview
- **Description**: Desktop application for single-cell microscopy analysis
- **Technology**: Python 3.12+ with tkinter GUI framework
- **Purpose**: TIFF stack visualization and fluorescence intensity time-course analysis
- **Architecture**: Event-driven GUI with plugin system

### Core Functionality

#### 1. Image Processing Tools

**Binarization (Phase Contrast)**
- `old/pyama/src/pyama/tools/binarize.py:10` - `binarize_phasecontrast_stack()` - Stack-level binarization
- `old/pyama/src/pyama/img_op/coarse_binarize_phc.py:56` - `binarize_frame()` - Frame-level algorithm using logarithmic standard deviation
- GUI: Tools → "Binarize…" (`old/pyama/src/pyama/session/view_tk.py:145`)

**Background Correction (Fluorescence)**
- `old/pyama/src/pyama/img_op/background_correction.py:87` - `background_schwarzfischer()` - Schwarzfischer et al. algorithm
- `old/pyama/src/pyama/tools/bgcorr.py:10` - `perform_background_correction()` - High-level wrapper
- GUI: Tools → "Background correction…" (`old/pyama/src/pyama/session/view_tk.py:147`)

**ROI Management**
- `old/pyama/src/pyama/tools/roi_bboxer.py:4` - `get_selected_bboxes()` - Maximum bounding box calculation
- `old/pyama/src/pyama/roi/` - ROI classes (ContourRoi, RectRoi)
- GUI: Tools → "Pickle maximum bounding box" (`old/pyama/src/pyama/session/view_tk.py:146`)

#### 2. Architecture Components

**MVC Pattern**
- `SessionModel`: Data management and state
- `SessionView_Tk`: tkinter-based UI
- `SessionController`: Business logic and event handling

**Key Classes**
- `StackViewer`: TIFF stack display with ROI selection
- `MetaStack`: Multi-channel stack composition from multiple files
- `RoiCollection`: Cell tracking and selection management
- `Tracker`: Frame-to-frame cell tracking
- `ModuleManager`: Plugin system architecture

**Stack Loading System**
- Multi-file, multi-channel composition
- Channel types: Phase contrast, Fluorescence, Segmentation
- Session save/load with ZIP format

#### 3. Plugin System
- Located in `old/pyama/plugins/`
- Modular architecture for extensibility
- Examples: `first_segmenter.py`, `load_grid.py`, `save_intensity.py`

### GUI Architecture

The application uses tkinter with an event-driven architecture:

```python
# Tools menu structure
self.toolmenu = tk.Menu(menubar)
menubar.add_cascade(label="Tools", menu=self.toolmenu)
self.toolmenu.add_command(label="Binarize…", command=self.binarize)
self.toolmenu.add_command(label="Background correction…", command=self._background_correction)
self.toolmenu.add_command(label="Pickle maximum bounding box", command=self._pickle_max_bbox)
```

## Fluorescence Fitting Library (`old/py_fit_fluorescence/`)

### Project Overview
- **Purpose**: Mathematical modeling and fitting of fluorescence protein maturation curves
- **Technology**: Scientific Python stack (NumPy, SciPy, matplotlib)
- **Models**: Gene expression with protein maturation kinetics

### Core Components

#### 1. Mathematical Models

**Maturation Model** (`models/maturation.py`)
- Three-stage gene expression: mRNA → immature protein → mature protein
- ODE system with parameters: t₀, k_tl, k_m, β, δ
- Based on research from doi:10.1016/j.nano.2019.102077

**Model Variants**
- `model_twostage.py`: Simplified two-stage model
- `model_threestage.py`: Full three-stage maturation model
- `models/maturation_blocked.py`: Maturation with blocking effects
- `models/trivial.py`: Simple exponential model

#### 2. Fitting Infrastructure

**Core Fitting** (`fit_prog.py`)
- Multi-start optimization using scipy.optimize
- Latin Hypercube Sampling (LHS) for initial parameter estimation
- Support for fixed parameters and parameter bounds
- Batch processing capabilities

**Parameter Management** (`fitparameters.py`)
- `FitParameters` class for parameter constraints and bounds
- Default values from literature
- Parameter validation and constraint handling

**Data I/O** (`ioutils.py`, `export.py`)
- Excel/CSV data loading
- Result export (Excel, PDF plots, histograms)
- Timestamp management for output files

#### 3. Mathematical Foundation

The core maturation model solves the ODE system:

```
∂M/∂t = -δM(t)                    [mRNA degradation]
∂G_u/∂t = k_tl·M(t) - k_m·G_u(t) - β·G_u(t)  [immature protein]
∂G/∂t = k_m·G_u(t) - β·G(t)      [mature protein]
```

With analytical solution documented in `Solution of maturation model ODE.ipynb`.

#### 4. Command-Line Interface

**Main Script** (`new_fitting.py`)
- Comprehensive CLI with argparse
- Excel/CSV file support
- Parameter file loading
- Batch processing mode
- Time unit conversion

**Usage Example**:
```bash
python new_fitting.py data.xlsx --model maturation --starts 10 --output results/
```

## Technology Stack Comparison

| Component | Legacy (old/) | Current (PyAMA-Qt) |
|-----------|---------------|---------------------|
| GUI Framework | tkinter | PySide6 (Qt) |
| Threading | Custom event system | QThread workers |
| Parallelism | Single-threaded | ProcessPoolExecutor |
| File I/O | Custom loaders | Memory-mapped arrays |
| Architecture | Plugin-based | Service/Utils separation |
| Type Hints | Minimal | Full Python 3.11+ style |
| Build System | setup.py style | Modern (hatchling) |

## Migration Notes

Key algorithms successfully migrated to PyAMA-Qt:
1. **Binarization**: Logarithmic standard deviation → `processing/utils/binarization.py`
2. **Background Correction**: Schwarzfischer algorithm → `processing/utils/background_correction.py`
3. **Cell Tracking**: Overlap-based tracking → `processing/utils/tracking.py`

The fluorescence fitting library (`py_fit_fluorescence/`) remains as a standalone analysis tool, complementing the main PyAMA-Qt processing pipeline.

## Analysis Jupyter Notebooks

### MergeSingleFiles.ipynb
- **Purpose**: Combines individual FOV fluorescence files into channel-based datasets
- **Input**: Separate CSV files per view field (e.g., `XY66/Fluorescence 2.csv`, `XY67/Fluorescence 2.csv`)
- **Output**: Merged channel files (`merged_ch1.csv`, `merged_ch2.csv`, etc.)
- **Key Features**:
  - Configurable channel mapping (first/last FOV positions per channel)
  - Exception handling for missing/excluded FOVs
  - Automated file path resolution and validation
- **Use Case**: Required for legacy PyAMA output format before automated channel merging

### PlotTraces.ipynb  
- **Purpose**: Visualizes fluorescence time-course traces from LISCA experiments
- **Input**: Merged channel CSV files (`merged_ch1.csv`, `merged_ch2.csv`, etc.)
- **Output**: Publication-ready plots (PNG/SVG/PDF formats)
- **Visualization Options**:
  - Individual single-cell traces with configurable styling
  - Mean traces with standard deviation bands
  - Multi-channel comparison plots (2x3 grid layout)
  - LMU corporate color scheme integration
- **Features**:
  - Customizable time intervals and total experiment duration
  - Flexible channel labeling for experimental conditions
  - High-resolution export (configurable DPI)
  - Both individual channel and comparative visualizations
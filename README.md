# PyAMA-Qt: Microscopy Image Analysis Suite

PyAMA-Qt is a comprehensive microscopy image analysis suite with three GUI applications for processing, visualization, and analysis of time-lapse microscopy data.

## Features

### Processing Application
- **ND2 File Support**: Native support for Nikon ND2 microscopy files
- **Multi-stage Pipeline**: Extract → Binarize → Correct → Track → Export
- **Parallel Processing**: True parallelism with process pools
- **Memory Efficient**: Memory-mapped arrays for large datasets
- **Batch Processing**: Configurable batch sizes for FOV processing

### Visualization Application
- **Interactive Trace Viewer**: Explore time-series cellular data
- **Multi-FOV Navigation**: Browse through fields of view
- **Image Display**: View raw and processed microscopy images
- **Lazy Loading**: On-demand data loading for performance
- **CSV Export**: Export analyzed trace data

### Analysis Application
- **Gene Expression Models**: Fit mathematical models to fluorescence traces
- **Multi-start Optimization**: Robust parameter estimation with Latin Hypercube Sampling
- **Parallel Fitting**: FOV-by-FOV processing with configurable worker pools
- **Three Model Types**: Maturation, two-stage, and trivial growth models
- **Comprehensive Export**: Results in CSV, Excel, PDF plots, and summary reports

## Installation

### Prerequisites
- Python 3.9 or higher
- Qt runtime (installed automatically with PySide6)

### Using uv (Recommended)
```bash
# Clone the repository
git clone https://github.com/yourusername/pyama-qt.git
cd pyama-qt

# Install with uv
uv sync

# Run processing application
uv run python -m pyama_qt process

# Run visualization application
uv run python -m pyama_qt viz

# Run analysis application
uv run python -m pyama_qt analysis
```

### Using pip
```bash
# Clone and install
git clone https://github.com/yourusername/pyama-qt.git
cd pyama-qt
pip install -e .

# Or install directly from GitHub
pip install git+https://github.com/yourusername/pyama-qt.git
```

## Usage

### Processing Application

Launch the processing GUI:
```bash
python -m pyama_qt process
```

**Workflow:**
1. **Load ND2 File**: Click "Load ND2 File" and select your microscopy data
2. **Set Output Directory**: Choose where to save processed results
3. **Configure Parameters**:
   - Select phase contrast and fluorescence channels
   - Set processing parameters (mask size, grid divisions)
   - Choose batch size for memory management
4. **Start Processing**: Click "Start Workflow" to begin
5. **Monitor Progress**: Watch real-time status updates for each FOV

**Output Structure:**
```
output_dir/
├── fov_0000/
│   ├── *_phase_contrast_raw.npy
│   ├── *_fluorescence_raw.npy
│   ├── *_binarized.npz
│   ├── *_fluorescence_corrected.npz
│   ├── *_traces.csv
│   └── *_traces_fitted.csv          # Analysis results
├── fov_0001/
│   └── ...
├── combined_fitting_results.csv      # Project-level results
├── analysis_summary.json             # Summary statistics
└── analysis_summary.xlsx             # Excel export with plots
```

### Visualization Application

Launch the visualization GUI:
```bash
python -m pyama_qt viz
```

**Workflow:**
1. **Load Project**: Click "Load Folder" and select a processed output directory
2. **Select FOV**: Choose a field of view from the list
3. **Explore Data**:
   - **Traces Tab**: View time-series plots of cellular measurements
   - **Images Tab**: Browse phase contrast and fluorescence images
   - Navigate through time points and channels
4. **Export Results**: Save plots or export data as needed

### Analysis Application

Launch the analysis GUI:
```bash
python -m pyama_qt analysis
```

**Three-Panel Interface:**
- **Left Panel**: CSV data loading and visualization of all traces
- **Middle Panel**: Fitting parameters and quality control with cell visualization
- **Right Panel**: Fitting quality metrics and parameter distributions

**Workflow:**
1. **Load Data**: Click "Load CSV" to load trace data
2. **Configure Fitting**:
   - Choose model type (maturation, two-stage, or trivial)
   - Optionally set initial parameters manually
   - Configure parallel processing settings
3. **Quality Control**: 
   - Visualize individual cells before fitting
   - Use "Shuffle" to randomly sample cells
4. **Run Analysis**: Click "Start Batch Fitting" to begin
5. **Review Results**: 
   - Check R² scores in quality plot
   - Examine parameter distributions
   - Export comprehensive reports

**Model Types:**
- **Maturation Model**: mRNA → immature protein → mature protein (5 parameters)
- **Two-stage Model**: Gene → immature protein → mature protein (5 parameters)  
- **Trivial Model**: Exponential growth with onset time (4 parameters)

## Configuration

### Processing Parameters

- **mask_size**: Binarization window size (default: 3)
- **div_horiz**: Horizontal grid divisions for background correction (default: 7)
- **div_vert**: Vertical grid divisions for background correction (default: 5)
- **min_trace_length**: Minimum frames for valid trace (default: 3)
- **batch_size**: Number of FOVs to extract before processing (default: 10)

### Memory Management

- **delete_raw_after_processing**: Remove raw NPY files after successful processing
- **batch_size**: Control memory usage by processing FOVs in batches
- **Memory-mapped arrays**: Large datasets are accessed without loading into RAM

## Technical Documentation

For detailed technical information, architecture details, and development guidelines, see [PROJECT.md](PROJECT.md).

## Development

### Quick Start
```bash
# Clone repository
git clone https://github.com/yourusername/pyama-qt.git
cd pyama-qt

# Install with development dependencies
uv sync --all-extras

# Run tests
uv run pytest

# Launch in development mode
uv run python -m pyama_qt process --debug
```

### Code Style
- Modern Python 3.9+ type hints (no typing imports for basic types)
- PySide6 for Qt bindings (use Signal, not pyqtSignal)
- Ruff for code formatting and linting
- Constrained layout for all matplotlib plots

## Scientific Methods

### Binarization Algorithm
- Logarithmic standard deviation method
- Optimized for phase contrast microscopy
- Numba JIT compilation for performance

### Background Correction
- Schwarzfischer algorithm implementation
- Grid-based background estimation
- Preserves cellular fluorescence signal

### Cell Tracking
- Overlap-based tracking between frames
- Consistent cell ID assignment
- Handles cell division and disappearance

### Trace Analysis
- **Mathematical Models**: Analytical solutions of gene expression ODEs
- **Multi-start Optimization**: Latin Hypercube Sampling for robust fitting
- **Parameter Bounds**: Biologically meaningful constraints on model parameters
- **Quality Metrics**: R-squared, residual analysis, and convergence statistics

## Requirements

Core dependencies:
- PySide6 >= 6.5
- numpy >= 1.24
- pandas >= 2.0
- nd2 >= 0.10
- numba >= 0.57
- scipy >= 1.10
- scikit-image >= 0.21

Visualization extras:
- matplotlib >= 3.7

Analysis extras:
- openpyxl >= 3.0 (Excel export)
- seaborn >= 0.11 (statistical plots)

## License

[Add your license here]

## Contributing

Contributions are welcome! Please read [PROJECT.md](PROJECT.md) for architecture details and coding standards.

## Support

For bugs, feature requests, or questions, please open an issue on GitHub.
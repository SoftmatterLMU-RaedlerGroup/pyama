# How to Use PyAMA-Core

PyAMA-Core is the core processing library that provides the underlying algorithms, data models, and utilities for microscopy image analysis. It's designed to be imported and used by higher-level applications like PyAMA-Pro and PyAMA-Air.

## Installation

```bash
# Install pyama-core
uv pip install -e pyama-core/
```

## Main Components

### I/O Utilities (`pyama_core.io`)

Load and work with microscopy data:

```python
from pyama_core.io import load_microscopy_file, MicroscopyMetadata

# Load microscopy file
_, metadata = load_microscopy_file("path/to/file.nd2")

# Access metadata
print(f"Number of FOVs: {metadata.n_fovs}")
print(f"Channels: {metadata.channel_names}")
print(f"Time points: {metadata.n_t}")
```

**Key Functions:**

- `load_microscopy_file()`: Load ND2 or CZI files
- `get_microscopy_frame()`: Extract single frames
- `get_microscopy_channel_stack()`: Get all frames for a channel
- `get_microscopy_time_stack()`: Get time series for specific position

### Processing Workflow (`pyama_core.processing.workflow`)

Run complete processing pipelines:

```python
from pyama_core.processing.workflow import run_complete_workflow
from pyama_core.types.processing import (
    ProcessingContext,
    ChannelSelection,
    Channels,
)

# Define channel selections
pc_selection = ChannelSelection(channel=0, features=["area", "aspect_ratio"])
fl_selection = ChannelSelection(channel=1, features=["intensity_total"])

channels = Channels(pc=pc_selection, fl=[fl_selection])

# Create processing context
context = ProcessingContext(
    output_dir=Path("output"),
    channels=channels,
    params={},
    time_units="min",
)

# Run workflow
success = run_complete_workflow(
    metadata=metadata,
    context=context,
    fov_start=0,
    fov_end=metadata.n_fovs - 1,
    batch_size=2,
    n_workers=2,
)
```

**Workflow Steps:**

1. **Copying**: Extract frames from ND2 to NPY format
2. **Segmentation**: Cell segmentation using LOG-STD approach
3. **Correction**: Background estimation for fluorescence channels (correction applied during feature extraction)
4. **Tracking**: Cell tracking across time points using IoU
5. **Extraction**: Feature extraction and trace generation to CSV

### Merge Processing (`pyama_core.processing.merge`)

Combine CSV files from multiple samples:

```python
from pyama_core.processing.merge import run_merge

# Merge results
message = run_merge(
    sample_yaml=Path("samples.yaml"),
    processing_results_yaml=Path("processing_results.yaml"),
    output_dir=Path("output"),
)
```

### Analysis (`pyama_core.analysis`)

Fit models to trace data:

```python
from pyama_core.analysis.fitting import fit_model
from pyama_core.analysis.models import get_model, list_models

# Get available models
print("Available models:", list_models())

# Fit a model
result = fit_model(
    model_type="maturation",
    t_data=time_array,
    y_data=intensity_array,
    user_params={"k": 0.1},
    user_bounds={"k": (0.01, 1.0)},
)

print(f"R²: {result.r_squared}")
print(f"Parameters: {result.params}")
```

**Available Models:**

- `trivial`: Constant model
- `maturation`: Exponential maturation model
- `maturation_blocked`: Blocked maturation model

### Feature Extraction (`pyama_core.processing.extraction.features`)

Extract features from images:

```python
from pyama_core.processing.extraction.features import (
    list_phase_features,
    list_fluorescence_features,
)

# Get available features
pc_features = list_phase_features()  # ['area', 'aspect_ratio']
fl_features = list_fluorescence_features()  # ['intensity_total']
```

**Built-in Features:**

- **Phase contrast**: `area`, `aspect_ratio`
- **Fluorescence**: `intensity_total`

## Key Data Structures

### MicroscopyMetadata

Metadata container for microscopy files:

```python
from pyama_core.io import MicroscopyMetadata

metadata: MicroscopyMetadata
metadata.n_fovs      # Number of fields of view
metadata.n_t         # Number of time points
metadata.n_channels  # Number of channels
metadata.channel_names  # List of channel names
metadata.shape       # Image shape (height, width)
```

### ProcessingContext

Configuration for workflow execution:

```python
from pyama_core.types.processing import ProcessingContext

context = ProcessingContext(
    output_dir=Path("output"),
    channels=Channels(...),
    params={"background_weight": 0.0},  # Background correction weight [0, 1] (default: 0.0 = no correction)
    time_units="min",
)
```

### ChannelSelection

Define channel and feature combinations:

```python
from pyama_core.types.processing import ChannelSelection

# Phase contrast selection
pc = ChannelSelection(channel=0, features=["area", "aspect_ratio"])

# Fluorescence selection
fl = ChannelSelection(channel=1, features=["intensity_total"])
```

## Extending PyAMA-Core

### Adding Custom Features

Create a new feature file in `pyama_core/processing/extraction/features/`:

```python
from pyama_core.processing.extraction.features import FeatureExtractor

@FeatureExtractor("my_feature")
def extract_my_feature(image, mask, context):
    """Extract custom feature from image and mask."""
    # Your extraction logic here
    return feature_value
```

### Adding Custom Models

Create a new model file in `pyama_core/analysis/models/`:

```python
from pyama_core.analysis.models import BaseModel

class MyModel(BaseModel):
    """Custom model for analysis."""

    def __init__(self):
        super().__init__()
        self.params = {"k": 0.1}
        self.bounds = {"k": (0.01, 1.0)}

    def __call__(self, t, **params):
        # Your model function
        return params["k"] * t
```

Register in `pyama_core/analysis/models/__init__.py`:

```python
from .my_model import MyModel

MODELS = {
    ...
    "my_model": MyModel(),
}
```

## API Reference

### Workflow Functions

- `run_complete_workflow()`: Execute full processing pipeline
- `ensure_context()`: Validate and normalize processing context

### I/O Functions

- `load_microscopy_file()`: Load microscopy metadata
- `get_microscopy_frame()`: Extract single frame
- `load_processing_results_yaml()`: Load processing results from YAML file

### Analysis Functions

- `fit_model()`: Fit analysis model to data
- `get_model()`: Get model instance by name
- `list_models()`: List available models

### Merge Functions

- `run_merge()`: Merge CSV files from multiple samples
- `parse_fov_range()`: Parse FOV range strings
- `read_samples_yaml()`: Load sample configuration

## Tips

- **Direct Import**: Import specific functions you need; avoid `import *`
- **Path Objects**: Use `pathlib.Path` for all file paths
- **Type Hints**: Check type hints in function signatures for parameter types
- **Context Managers**: Use existing context structures rather than creating custom ones
- **Extension Points**: Leverage plugin system for features and models
- **Error Handling**: Check return values and catch exceptions appropriately

## Examples

See the tests directory for working examples:

- `tests/test_workflow.py`: End-to-end workflow execution
- `tests/test_merge.py`: Merge operations
- `tests/test_results_yaml.py`: Results file handling

## Integration

PyAMA-Core is designed to be:

- **Importable**: Use in Python scripts and notebooks
- **Extensible**: Add custom features and models via plugins
- **Testable**: Comprehensive test suite included
- **Documented**: Type hints and docstrings throughout

For applications built on top of PyAMA-Core:

- **PyAMA-Pro**: Full-featured Qt GUI with comprehensive visualization and analysis tools
- **PyAMA-Air**: Guided workflow wizards (both CLI and GUI) for quick configuration and execution

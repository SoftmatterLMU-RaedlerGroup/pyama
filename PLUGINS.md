# Plugin Systems

PyAMA supports two plugin systems: feature plugins for extraction and model plugins for analysis.

## Feature Plugin System

The extraction features module uses an automatic plugin discovery system. To add a new feature, create a Python file in `pyama-core/src/pyama_core/processing/extraction/features/` with the required metadata.

## Creating a New Feature

### Quick Start

Copy `aspect_ratio.py` (the example feature) and modify it:

```bash
cp pyama-core/src/pyama_core/processing/extraction/features/aspect_ratio.py \
   pyama-core/src/pyama_core/processing/extraction/features/my_feature.py
```

Edit the file:

- Change `FEATURE_NAME` to your feature name
- Change `FEATURE_TYPE` if needed ("phase" or "fluorescence")
- Implement your `extract_*` function

### Manual Creation

Create a new file: `my_feature.py`

```python
"""My custom feature extraction."""

import numpy as np

from pyama_core.processing.extraction.features.context import ExtractionContext

# Feature metadata (required for auto-discovery)
FEATURE_TYPE = "phase"  # or "fluorescence"
FEATURE_NAME = "my_feature"


def extract_my_feature(ctx: ExtractionContext) -> np.float32:
    """Extract my custom feature for a single cell."""
    mask = ctx.mask.astype(bool, copy=False)
    return np.sum(mask) * 2.0  # Example: double the area
```

### 2. Required Components

Each feature module must have:

- **FEATURE_TYPE** (str): Either `"phase"` or `"fluorescence"`
  - `"phase"`: Feature operates on segmentation masks (phase contrast)
  - `"fluorescence"`: Feature operates on intensity images (fluorescence channels)

- **FEATURE_NAME** (str): Unique identifier for the feature (e.g., `"my_feature"`)

- **extract_{FEATURE_NAME}()** function: The extractor function that takes an `ExtractionContext` and returns a numeric value

### 3. Feature Type Guidelines

**Phase Features** (`FEATURE_TYPE = "phase"`):

- Operate on segmentation masks derived from phase contrast images
- Use `ctx.mask` to access the cell mask
- Examples: `area`, `perimeter`, `eccentricity`

**Fluorescence Features** (`FEATURE_TYPE = "fluorescence"`):

- Operate on intensity images from fluorescence channels
- Use `ctx.image` to access the intensity data
- Examples: `intensity_total`, `intensity_mean`, `intensity_max`

### 4. Auto-Discovery

Once you create the file with the required metadata, it will be automatically discovered and registered when the module is imported. No additional configuration needed!

### 5. Testing Your Feature

```python
from pyama_core.processing.extraction.features import (
    list_features,
    list_phase_features,
    list_fluorescence_features,
    get_feature_extractor,
)

# Check if your feature is registered
print(list_features())  # Should include "my_feature"
print(list_phase_features())  # If FEATURE_TYPE="phase"

# Get the extractor function
extractor = get_feature_extractor("my_feature")
```

## ExtractionContext

The `ExtractionContext` dataclass contains the data needed for feature extraction:

```python
@dataclass
class ExtractionContext:
    image: np.ndarray      # 2D intensity image (for fluorescence features)
    mask: np.ndarray       # 2D binary mask of the cell (for phase features)
```

- **image**: 2D numpy array of pixel intensities (used by fluorescence features)
- **mask**: 2D numpy array with non-zero values for pixels belonging to the cell (used by phase features)

## Model Plugin System

The analysis models module uses an automatic plugin discovery system. To add a new model, create a Python file in `pyama-core/src/pyama_core/analysis/models/` with the required metadata.

### Creating a New Model

#### Quick Start

Copy `trivial.py` (the example model) and modify it:

```bash
cp pyama-core/src/pyama_core/analysis/models/trivial.py \
   pyama-core/src/pyama_core/analysis/models/my_model.py
```

Edit the file:

- Change `MODEL_NAME` to your model name
- Implement your `fit` and `predict` methods

#### Manual Creation

Create a new file: `my_model.py`

```python
"""My custom analysis model."""

import numpy as np
from typing import Dict, Any

from pyama_core.analysis.models.base import BaseModel

# Model metadata (required for auto-discovery)
MODEL_NAME = "my_model"


class MyModel(BaseModel):
    """My custom analysis model."""
    
    def fit(self, data: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Fit the model to data."""
        # Implement your fitting logic
        return {"status": "success", "parameters": {}}
    
    def predict(self, data: np.ndarray, **kwargs) -> np.ndarray:
        """Make predictions using the fitted model."""
        # Implement your prediction logic
        return np.zeros_like(data)
```

### Required Components

Each model module must have:

- **MODEL_NAME** (str): Unique identifier for the model (e.g., `"my_model"`)

- **Model class**: A class that inherits from `BaseModel` and implements:
  - `fit(data, **kwargs)`: Fit the model to data, return status and parameters
  - `predict(data, **kwargs)`: Make predictions using the fitted model

### BaseModel Interface

The `BaseModel` class provides the interface that all models must implement:

```python
class BaseModel:
    def fit(self, data: np.ndarray, **kwargs) -> Dict[str, Any]:
        """Fit the model to data."""
        raise NotImplementedError
    
    def predict(self, data: np.ndarray, **kwargs) -> np.ndarray:
        """Make predictions using the fitted model."""
        raise NotImplementedError
```

### Auto-Discovery

Once you create the file with the required metadata, it will be automatically discovered and registered when the module is imported. No additional configuration needed!

### Testing Your Model

```python
from pyama_core.analysis.models import (
    list_models,
    get_model_class,
)

# Check if your model is registered
print(list_models())  # Should include "my_model"

# Get the model class
model_class = get_model_class("my_model")
model = model_class()
```

"""
Simple functional models for curve fitting.
"""

from . import trivial
from . import maturation
from . import maturation_blocked

# Model registry - automatically discovers available models
MODELS = {
    'trivial': trivial,
    'maturation': maturation,
    'maturation_blocked': maturation_blocked,
}

def get_model(model_name: str):
    """
    Get a model module by name.
    
    Args:
        model_name: Name of the model ('trivial', 'maturation', etc.)
    
    Returns:
        Model module with eval, DEFAULTS, and BOUNDS attributes
    
    Raises:
        ValueError: If model_name is not found
    """
    if model_name not in MODELS:
        available = ', '.join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return MODELS[model_name]

def get_types(model_name: str):
    """
    Get TypedDict classes from a model.
    
    Args:
        model_name: Name of the model ('trivial', 'maturation', etc.)
    
    Returns:
        Dictionary containing TypedDict classes:
        - 'Params': All model parameters
        - 'Bounds': Parameter bounds
        - 'UserParams': User-modifiable parameters
        - 'UserBounds': User parameter bounds
    
    Raises:
        ValueError: If model_name is not found
    """
    model = get_model(model_name)
    return {
        'Params': model.Params,
        'Bounds': model.Bounds,
        'UserParams': model.UserParams,
        'UserBounds': model.UserBounds,
    }

def list_models():
    """Return list of available model names."""
    return list(MODELS.keys())

__all__ = [
    'get_model',
    'get_types',
    'list_models',
    'MODELS',
]

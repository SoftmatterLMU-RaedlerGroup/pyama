"""
Simple functional models for curve fitting.
"""

from pyama_core.analysis.models import maturation

MODELS = {
    "maturation": maturation,
}


def get_model(model_name: str):
    if model_name not in MODELS:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return MODELS[model_name]


def get_types(model_name: str):
    """Get type classes for a model.
    
    Returns UserParams and UserBounds for validation.
    Models with FixedParams/FitParams structure will have these types.
    """
    model = get_model(model_name)
    types = {}
    
    # Check for new structure (FixedParams/FitParams)
    if hasattr(model, "UserParams"):
        types["UserParams"] = model.UserParams
    if hasattr(model, "UserBounds"):
        types["UserBounds"] = model.UserBounds
    
    return types


def list_models() -> list[str]:
    """Return all registered model names."""
    return list(MODELS.keys())


def register_plugin_model(model_name: str, model_module: object) -> None:
    """Register a plugin model at runtime.

    Args:
        model_name: Name of the model (e.g., "exponential_decay")
        model_module: Module with Params, Bounds, DEFAULTS, BOUNDS, eval

    Raises:
        ValueError: If model_name already registered or module is invalid
    """
    if model_name in MODELS:
        raise ValueError(
            f"Model '{model_name}' is already registered. "
            f"Plugin models must have unique names."
        )

    # Verify required components
    required = ["Params", "Bounds", "DEFAULTS", "BOUNDS", "eval"]
    for attr in required:
        if not hasattr(model_module, attr):
            raise ValueError(f"Model module missing required attribute: {attr}")

    MODELS[model_name] = model_module


__all__ = [
    "get_model",
    "get_types",
    "list_models",
    "register_plugin_model",
    "MODELS",
]

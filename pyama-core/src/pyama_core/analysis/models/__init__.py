"""
Simple functional models for curve fitting.
"""

from pyama_core.analysis.models import maturation
from pyama_core.analysis.models import maturation_blocked
from pyama_core.analysis.models import trivial

MODELS = {
    "trivial": trivial,
    "maturation": maturation,
    # "maturation_blocked": maturation_blocked,
}


def get_model(model_name: str):
    if model_name not in MODELS:
        available = ", ".join(MODELS.keys())
        raise ValueError(f"Unknown model: {model_name}. Available models: {available}")
    return MODELS[model_name]


def get_types(model_name: str):
    model = get_model(model_name)
    return {
        "Params": model.Params,
        "Bounds": model.Bounds,
        "UserParams": model.UserParams,
        "UserBounds": model.UserBounds,
    }


def list_models():
    return list(MODELS.keys())


__all__ = [
    "get_model",
    "get_types",
    "list_models",
    "MODELS",
]

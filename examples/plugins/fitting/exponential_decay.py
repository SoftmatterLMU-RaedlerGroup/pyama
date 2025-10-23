"""Example analysis model: Simple exponential decay.

A plugin model for cell dynamics fitting.
Demonstrates the model plugin interface for time-series analysis.
"""

from dataclasses import dataclass
import numpy as np


PLUGIN_NAME = "exponential_decay"
PLUGIN_TYPE = "model"
PLUGIN_VERSION = "1.0.0"


@dataclass(slots=True)
class Params:
    """Model parameters to be fitted."""
    t0: float
    amplitude: float
    decay_rate: float
    offset: float


@dataclass(slots=True)
class Bounds:
    """Bounds for each parameter."""
    t0: tuple[float, float]
    amplitude: tuple[float, float]
    decay_rate: tuple[float, float]
    offset: tuple[float, float]


@dataclass(slots=True)
class UserParams:
    """User-configurable parameters (subset of Params)."""
    amplitude: float | None = None
    decay_rate: float | None = None


@dataclass(slots=True)
class UserBounds:
    """User-configurable bounds."""
    amplitude: tuple[float, float] | None = None
    decay_rate: tuple[float, float] | None = None


# Default parameter values
DEFAULTS = Params(
    t0=0.0,
    amplitude=100.0,
    decay_rate=0.1,
    offset=10.0,
)

# Parameter bounds for fitting
BOUNDS = Bounds(
    t0=(0.0, 100.0),
    amplitude=(1.0, 10000.0),
    decay_rate=(0.001, 1.0),
    offset=(-1000.0, 1000.0),
)


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    """Evaluate the exponential decay model.

    Model: f(t) = amplitude * exp(-decay_rate * (t - t0)) + offset (for t >= t0)
           f(t) = amplitude + offset (for t < t0)

    Args:
        t: Time points (1D array)
        params: Model parameters

    Returns:
        Model predictions at time points
    """
    t = np.asarray(t, dtype=np.float32)
    dt = t - params.t0

    # Exponential decay starting at t0
    decay = params.amplitude * np.exp(-params.decay_rate * dt)
    result = np.where(dt >= 0, decay, params.amplitude)

    return result + params.offset

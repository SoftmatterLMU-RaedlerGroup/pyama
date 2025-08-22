"""
Trivial model: Simple gene expression dynamics.
"""

import numpy as np
from typing import TypedDict, Tuple

# TypedDict for all model parameters
class Params(TypedDict):
    """All model parameters."""
    t0: float
    ktl: float
    delta: float
    beta: float

# TypedDict for parameter bounds
class Bounds(TypedDict):
    """Bounds for all model parameters."""
    t0: Tuple[float, float]
    ktl: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]

# TypedDict for user-modifiable parameters (excludes t0)
class UserParams(TypedDict, total=False):
    """Parameters that can be modified by the user in the GUI."""
    ktl: float
    delta: float
    beta: float

# TypedDict for user parameter bounds
class UserBounds(TypedDict):
    """Bounds for user-modifiable parameters."""
    ktl: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]

# Default values
DEFAULTS: Params = {
    't0': 0,
    'ktl': 1e3,
    'delta': 0.07,
    'beta': 0.0436275356035,
}

# Parameter bounds
BOUNDS: Bounds = {
    't0': (0, 30),
    'ktl': (1, 5e4),
    'delta': (1e-5, 10.1),
    'beta': (1e-5, 10),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    """
    Evaluate trivial model at time points t.
    
    Args:
        t: Time points (numpy array)
        params: Model parameters as TypedDict
    
    Returns:
        Fluorescence intensity at time points t
    """
    # Destructure parameters
    t0 = params['t0']
    ktl = params['ktl']
    delta = params['delta']
    beta = params['beta']
    
    dt = t - t0
    dmb = delta - beta
    
    # Direct computation
    result = ktl / dmb * (1 - np.exp(-dmb * dt)) * np.exp(-beta * dt)
    
    # Apply ReLU: zero before t0, result after t0
    return np.where(dt > 0, result, 0)
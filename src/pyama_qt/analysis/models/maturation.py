"""
Maturation model: Gene expression with protein maturation.

Literature values from Table 1 of doi:10.1016/j.nano.2019.102077
"""

import numpy as np
from typing import TypedDict, Tuple

# TypedDict for all model parameters
class Params(TypedDict):
    """All model parameters."""
    t0: float
    ktl: float
    km: float
    delta: float
    beta: float

# TypedDict for parameter bounds
class Bounds(TypedDict):
    """Bounds for all model parameters."""
    t0: Tuple[float, float]
    ktl: Tuple[float, float]
    km: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]

# TypedDict for user-modifiable parameters (excludes t0)
class UserParams(TypedDict, total=False):
    """Parameters that can be modified by the user in the GUI."""
    ktl: float
    km: float
    delta: float
    beta: float

# TypedDict for user parameter bounds
class UserBounds(TypedDict):
    """Bounds for user-modifiable parameters."""
    ktl: Tuple[float, float]
    km: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]

# Default values (km and beta from literature)
DEFAULTS: Params = {
    't0': 0,
    'ktl': 1e3,
    'km': 1.28,      # Maturation rate from literature
    'delta': 1e-2,   # Transport rate
    'beta': 5.22e-3, # Degradation rate from literature
}

# Parameter bounds
BOUNDS: Bounds = {
    't0': (0, 30),
    'ktl': (1, 5e8),
    'km': (1e-5, 30),
    'delta': (1e-5, 11),
    'beta': (1e-5, 10),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    """
    Evaluate maturation model at time points t.
    
    Models fluorescent protein expression with maturation step.
    
    Args:
        t: Time points (numpy array)
        params: Model parameters as TypedDict
    
    Returns:
        Fluorescence intensity at time points t
    """
    # Destructure parameters
    t0 = params['t0']
    ktl = params['ktl']
    km = params['km']
    delta = params['delta']
    beta = params['beta']
    
    dt = t - t0
    bmd = beta - delta
    
    # Three-term expression for mature protein concentration
    f1 = np.exp(-(beta + km) * dt) / (bmd + km)
    f2 = -np.exp(-beta * dt) / bmd
    f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)
    
    result = (f1 + f2 + f3) * ktl
    
    # Apply ReLU: zero before t0, result after t0
    return np.where(dt > 0, result, 0)
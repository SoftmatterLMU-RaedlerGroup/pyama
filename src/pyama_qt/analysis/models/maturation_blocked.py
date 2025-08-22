"""
Maturation blocked model: Decay dynamics after maturation inhibition.

Literature values from Table 1 of doi:10.1016/j.nano.2019.102077
"""

import numpy as np
from typing import TypedDict, Tuple

# TypedDict for all model parameters
class Params(TypedDict):
    """All model parameters."""
    t0: float
    G0: float
    Gu0: float
    km: float
    beta: float

# TypedDict for parameter bounds
class Bounds(TypedDict):
    """Bounds for all model parameters."""
    t0: Tuple[float, float]
    G0: Tuple[float, float]
    Gu0: Tuple[float, float]
    km: Tuple[float, float]
    beta: Tuple[float, float]

# TypedDict for user-modifiable parameters (excludes t0)
class UserParams(TypedDict, total=False):
    """Parameters that can be modified by the user in the GUI."""
    G0: float
    Gu0: float
    km: float
    beta: float

# TypedDict for user parameter bounds
class UserBounds(TypedDict):
    """Bounds for user-modifiable parameters."""
    G0: Tuple[float, float]
    Gu0: Tuple[float, float]
    km: Tuple[float, float]
    beta: Tuple[float, float]

# Default values
DEFAULTS: Params = {
    't0': 0,         # Time of maturation block
    'G0': 100.0,     # Mature protein at t0
    'Gu0': 100.0,    # Immature protein production rate
    'km': 1.28,      # Maturation rate from literature
    'beta': 5.22e-3, # Degradation rate from literature
}

# Parameter bounds
BOUNDS: Bounds = {
    't0': (0, 30),
    'G0': (0, 1e6),
    'Gu0': (0, 1e6),
    'km': (1e-5, 30),
    'beta': (1e-5, 10),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    """
    Evaluate maturation blocked model at time points t.
    
    Models decay after maturation is chemically blocked.
    
    Args:
        t: Time points (numpy array)
        params: Model parameters as TypedDict
    
    Returns:
        Fluorescence intensity at time points t
    """
    # Destructure parameters
    t0 = params['t0']
    G0 = params['G0']
    Gu0 = params['Gu0']
    km = params['km']
    beta = params['beta']
    
    dt = t - t0
    
    # Decay of mature protein + accumulation of immature protein
    result = G0 * np.exp(-beta * dt) + Gu0 * (np.exp(-beta * dt) - np.exp(-(beta + km) * dt))
    
    # Apply ReLU: zero before t0, result after t0
    return np.where(dt > 0, result, 0)
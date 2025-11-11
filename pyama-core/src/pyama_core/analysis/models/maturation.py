"""
Maturation model: Gene expression with protein maturation.
"""

import numpy as np

from pyama_core.types.analysis import FixedParam, FitParam, FixedParams, FitParams


# Default fixed parameters
DEFAULT_FIXED: FixedParams = {
    "km": FixedParam(name="Maturation Rate", value=1.28),
    "beta": FixedParam(name="Degradation Rate", value=5.22e-3),
    "scale": FixedParam(name="Scale Factor", value=1.0),
}


# Default fit parameters
DEFAULT_FIT: FitParams = {
    "t0": FitParam(name="Time Zero", value=0, lb=-1, ub=1),
    "ktl": FitParam(name="Translation Rate", value=1e3, lb=1, ub=5e8),
    "delta": FitParam(name="Decay Rate", value=1e-2, lb=1e-5, ub=11),
    "offset": FitParam(name="Baseline Offset", value=0, lb=-1e6, ub=1e6),
}


def eval(t: np.ndarray, fixed: FixedParams, fit: FitParams) -> np.ndarray:
    """Evaluate the maturation model.
    
    Args:
        t: Time array
        fixed: Fixed parameters dict (km, beta, scale)
        fit: Fitted parameters dict (t0, ktl, delta, offset)
    
    Returns:
        Model predictions
    """
    t0 = fit["t0"].value
    ktl = fit["ktl"].value
    km = fixed["km"].value
    delta = fit["delta"].value
    beta = fixed["beta"].value
    offset = fit["offset"].value
    scale = fixed["scale"].value

    dt = t - t0
    bmd = beta - delta

    f1 = np.exp(-(beta + km) * dt) / (bmd + km)
    f2 = -np.exp(-beta * dt) / bmd
    f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)

    result = (f1 + f2 + f3) * ktl
    normalized_result = np.where(dt > 0, result, 0)
    scaled_result = scale * (normalized_result + offset)
    return scaled_result



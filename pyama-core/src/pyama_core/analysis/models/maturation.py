"""
Maturation model: Gene expression with protein maturation.
"""

import numpy as np
from typing import TypedDict, Tuple


class Params(TypedDict):
    t0: float
    ktl: float
    km: float
    delta: float
    beta: float


class Bounds(TypedDict):
    t0: Tuple[float, float]
    ktl: Tuple[float, float]
    km: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]


class UserParams(TypedDict, total=False):
    ktl: float
    km: float
    delta: float
    beta: float


class UserBounds(TypedDict):
    ktl: Tuple[float, float]
    km: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]


DEFAULTS: Params = {
    't0': 0,
    'ktl': 1e3,
    'km': 1.28,
    'delta': 1e-2,
    'beta': 5.22e-3,
}


BOUNDS: Bounds = {
    't0': (0, 30),
    'ktl': (1, 5e8),
    'km': (1e-5, 30),
    'delta': (1e-5, 11),
    'beta': (1e-5, 10),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params['t0']
    ktl = params['ktl']
    km = params['km']
    delta = params['delta']
    beta = params['beta']

    dt = t - t0
    bmd = beta - delta

    f1 = np.exp(-(beta + km) * dt) / (bmd + km)
    f2 = -np.exp(-beta * dt) / bmd
    f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)

    result = (f1 + f2 + f3) * ktl
    return np.where(dt > 0, result, 0)



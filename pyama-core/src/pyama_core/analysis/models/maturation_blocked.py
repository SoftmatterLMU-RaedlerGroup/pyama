"""
Maturation blocked model: Decay dynamics after maturation inhibition.
"""

import numpy as np
from typing import TypedDict, Tuple


class Params(TypedDict):
    t0: float
    G0: float
    Gu0: float
    km: float
    beta: float
    offset: float


class Bounds(TypedDict):
    t0: Tuple[float, float]
    G0: Tuple[float, float]
    Gu0: Tuple[float, float]
    km: Tuple[float, float]
    beta: Tuple[float, float]
    offset: Tuple[float, float]


class UserParams(TypedDict, total=False):
    G0: float
    Gu0: float
    km: float
    beta: float


class UserBounds(TypedDict):
    G0: Tuple[float, float]
    Gu0: Tuple[float, float]
    km: Tuple[float, float]
    beta: Tuple[float, float]


DEFAULTS: Params = {
    't0': 0,
    'G0': 100.0,
    'Gu0': 100.0,
    'km': 1.28,
    'beta': 5.22e-3,
    'offset': 0,
}


BOUNDS: Bounds = {
    't0': (0, 1),
    'G0': (0, 1e6),
    'Gu0': (0, 1e6),
    'km': (1e-5, 30),
    'beta': (1e-5, 10),
    'offset': (-1e6, 1e6),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params['t0']
    G0 = params['G0']
    Gu0 = params['Gu0']
    km = params['km']
    beta = params['beta']
    offset = params['offset']

    dt = t - t0
    result = G0 * np.exp(-beta * dt) + Gu0 * (np.exp(-beta * dt) - np.exp(-(beta + km) * dt))
    base = np.where(dt > 0, result, 0)
    return base + offset



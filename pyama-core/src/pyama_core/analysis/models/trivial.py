"""
Trivial model: Simple gene expression dynamics.
"""

import numpy as np
from typing import TypedDict, Tuple


class Params(TypedDict):
    t0: float
    ktl: float
    delta: float
    beta: float


class Bounds(TypedDict):
    t0: Tuple[float, float]
    ktl: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]


class UserParams(TypedDict, total=False):
    ktl: float
    delta: float
    beta: float


class UserBounds(TypedDict):
    ktl: Tuple[float, float]
    delta: Tuple[float, float]
    beta: Tuple[float, float]


DEFAULTS: Params = {
    't0': 0,
    'ktl': 1e3,
    'delta': 0.07,
    'beta': 0.0436275356035,
}


BOUNDS: Bounds = {
    't0': (0, 30),
    'ktl': (1, 5e4),
    'delta': (1e-5, 10.1),
    'beta': (1e-5, 10),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params['t0']
    ktl = params['ktl']
    delta = params['delta']
    beta = params['beta']

    dt = t - t0
    dmb = delta - beta
    result = ktl / dmb * (1 - np.exp(-dmb * dt)) * np.exp(-beta * dt)
    return np.where(dt > 0, result, 0)



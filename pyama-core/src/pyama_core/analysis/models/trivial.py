"""
Trivial model: Simple gene expression dynamics.
"""

import numpy as np
from typing import TypedDict


class Params(TypedDict):
    t0: float
    ktl: float
    delta: float
    beta: float
    offset: float


class Bounds(TypedDict):
    t0: tuple[float, float]
    ktl: tuple[float, float]
    delta: tuple[float, float]
    beta: tuple[float, float]
    offset: tuple[float, float]


class UserParams(TypedDict, total=False):
    ktl: float
    delta: float
    beta: float


class UserBounds(TypedDict):
    ktl: tuple[float, float]
    delta: tuple[float, float]
    beta: tuple[float, float]


DEFAULTS: Params = {
    't0': 2.0,
    'ktl': 20.0,
    'delta': 0.07,
    'beta': 0.0436275356035,
    'offset': 0.0,
}


BOUNDS: Bounds = {
    't0': (-np.inf, 30.0),
    'ktl': (1.0, 5e4),
    'delta': (1e-5, 10.1),
    'beta': (1e-5, 10.0),
    'offset': (-1e6, 1e6),
}


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params['t0']
    ktl = params['ktl']
    delta = params['delta']
    beta = params['beta']
    offset = params['offset']

    dt = t - t0
    dmb = delta - beta

    result = (ktl / dmb) * (1.0 - np.exp(-dmb * dt)) * np.exp(-beta * dt)
    base = np.where(dt > 0, result, 0)
    return offset + base



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
    't0': (0.0, 30.0),
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

    # Time since onset; no signal before t0
    dt = np.maximum(t - t0, 0.0)

    # Handle the delta ≈ beta case stably using the limit
    dmb = delta - beta
    eps = 1e-8

    # General-case expression
    general = (ktl / dmb) * (1.0 - np.exp(-dmb * dt)) * np.exp(-beta * dt)

    # Limit as delta -> beta
    limit = ktl * dt * np.exp(-beta * dt)

    result = np.where(np.abs(dmb) < eps, limit, general)

    # Numerical safety: enforce non-negativity like the legacy implementation
    return offset + np.clip(result, 0.0, None)



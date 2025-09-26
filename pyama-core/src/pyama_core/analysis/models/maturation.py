"""
Maturation model: Gene expression with protein maturation.
"""

from dataclasses import dataclass
import numpy as np


@dataclass(slots=True)
class Params:
    t0: float
    ktl: float
    km: float
    delta: float
    beta: float
    offset: float


@dataclass(slots=True)
class Bounds:
    t0: tuple[float, float]
    ktl: tuple[float, float]
    km: tuple[float, float]
    delta: tuple[float, float]
    beta: tuple[float, float]
    offset: tuple[float, float]


@dataclass(slots=True)
class UserParams:
    ktl: float | None = None
    km: float | None = None
    delta: float | None = None
    beta: float | None = None


@dataclass(slots=True)
class UserBounds:
    ktl: tuple[float, float] | None = None
    km: tuple[float, float] | None = None
    delta: tuple[float, float] | None = None
    beta: tuple[float, float] | None = None


DEFAULTS = Params(
    t0=0,
    ktl=1e3,
    km=1.28,
    delta=1e-2,
    beta=5.22e-3,
    offset=0,
)


BOUNDS = Bounds(
    t0=(0, 1),
    ktl=(1, 5e8),
    km=(1e-5, 30),
    delta=(1e-5, 11),
    beta=(1e-5, 10),
    offset=(-1e6, 1e6),
)


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params.t0
    ktl = params.ktl
    km = params.km
    delta = params.delta
    beta = params.beta
    offset = params.offset

    dt = t - t0
    bmd = beta - delta

    f1 = np.exp(-(beta + km) * dt) / (bmd + km)
    f2 = -np.exp(-beta * dt) / bmd
    f3 = km / bmd / (bmd + km) * np.exp(-delta * dt)

    result = (f1 + f2 + f3) * ktl
    base = np.where(dt > 0, result, 0)
    return base + offset

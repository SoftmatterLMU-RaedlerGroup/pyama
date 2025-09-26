"""
Maturation blocked model: Decay dynamics after maturation inhibition.
"""

from dataclasses import dataclass
import numpy as np


@dataclass(slots=True)
class Params:
    t0: float
    G0: float
    Gu0: float
    km: float
    beta: float
    offset: float


@dataclass(slots=True)
class Bounds:
    t0: tuple[float, float]
    G0: tuple[float, float]
    Gu0: tuple[float, float]
    km: tuple[float, float]
    beta: tuple[float, float]
    offset: tuple[float, float]


@dataclass(slots=True)
class UserParams:
    G0: float | None = None
    Gu0: float | None = None
    km: float | None = None
    beta: float | None = None


@dataclass(slots=True)
class UserBounds:
    G0: tuple[float, float] | None = None
    Gu0: tuple[float, float] | None = None
    km: tuple[float, float] | None = None
    beta: tuple[float, float] | None = None


DEFAULTS = Params(
    t0=0,
    G0=100.0,
    Gu0=100.0,
    km=1.28,
    beta=5.22e-3,
    offset=0,
)


BOUNDS = Bounds(
    t0=(0, 1),
    G0=(0, 1e6),
    Gu0=(0, 1e6),
    km=(1e-5, 30),
    beta=(1e-5, 10),
    offset=(-1e6, 1e6),
)


def eval(t: np.ndarray, params: Params) -> np.ndarray:
    t0 = params.t0
    G0 = params.G0
    Gu0 = params.Gu0
    km = params.km
    beta = params.beta
    offset = params.offset

    dt = t - t0
    result = G0 * np.exp(-beta * dt) + Gu0 * (
        np.exp(-beta * dt) - np.exp(-(beta + km) * dt)
    )
    base = np.where(dt > 0, result, 0)
    return base + offset

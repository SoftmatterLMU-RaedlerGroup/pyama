"""
Two-stage gene expression model.

Simplified model without separate mRNA dynamics.
Models: Gene → immature protein → mature protein
"""

import numpy as np
from .base import ModelBase


class TwoStageModel(ModelBase):
    """
    Two-stage model for fluorescence protein expression.

    Simplified version without explicit mRNA dynamics.
    Models direct translation followed by maturation.

    Parameters:
        t0: Onset time of gene expression
        k_tl: Translation rate constant
        k_m: Maturation rate constant
        beta: Protein degradation rate
        offset: Baseline fluorescence offset
    """

    _DEFAULT_VALUES = {
        "t0": 2.0,
        "k_tl": 1000.0,
        "k_m": 1.28,
        "beta": 5.22e-3,
        "offset": 0.0,
    }

    _DEFAULT_BOUNDS = {
        "t0": (0.0, 30.0),
        "k_tl": (1.0, 5e8),
        "k_m": (1e-5, 30.0),
        "beta": (1e-5, 10.0),
        "offset": (-1000.0, 1000.0),
    }

    def __init__(self):
        super().__init__()

        self.params = {
            "t0": {
                "values": [self._DEFAULT_VALUES["t0"]],
                "min": self._DEFAULT_BOUNDS["t0"][0],
                "max": self._DEFAULT_BOUNDS["t0"][1],
                "fixed": False,
            },
            "k_tl": {
                "values": [self._DEFAULT_VALUES["k_tl"]],
                "min": self._DEFAULT_BOUNDS["k_tl"][0],
                "max": self._DEFAULT_BOUNDS["k_tl"][1],
                "fixed": False,
            },
            "k_m": {
                "values": [self._DEFAULT_VALUES["k_m"]],
                "min": self._DEFAULT_BOUNDS["k_m"][0],
                "max": self._DEFAULT_BOUNDS["k_m"][1],
                "fixed": False,
            },
            "beta": {
                "values": [self._DEFAULT_VALUES["beta"]],
                "min": self._DEFAULT_BOUNDS["beta"][0],
                "max": self._DEFAULT_BOUNDS["beta"][1],
                "fixed": False,
            },
            "offset": {
                "values": [self._DEFAULT_VALUES["offset"]],
                "min": self._DEFAULT_BOUNDS["offset"][0],
                "max": self._DEFAULT_BOUNDS["offset"][1],
                "fixed": False,
            },
        }

    @property
    def param_names(self) -> list[str]:
        """Return list of parameter names."""
        return ["t0", "k_tl", "k_m", "beta", "offset"]

    @property
    def default_bounds(self) -> dict[str, tuple[float, float]]:
        """Return default parameter bounds."""
        return self._DEFAULT_BOUNDS.copy()

    @property
    def default_values(self) -> dict[str, float]:
        """Return default parameter values."""
        return self._DEFAULT_VALUES.copy()

    def evaluate(
        self,
        t: np.ndarray,
        t0: float,
        k_tl: float,
        k_m: float,
        beta: float,
        offset: float = 0.0,
    ) -> np.ndarray:
        """
        Evaluate the two-stage model.

        Args:
            t: Array of time points
            t0: Onset time of gene expression
            k_tl: Translation rate constant
            k_m: Maturation rate constant
            beta: Protein degradation rate
            offset: Baseline fluorescence offset

        Returns:
            Model values at time points
        """
        t = np.asarray(t)
        f = np.zeros_like(t, dtype=float)

        # Only evaluate for times after onset
        idx_after = t > t0
        if not np.any(idx_after):
            return f + offset

        dt = t[idx_after] - t0

        # Two-stage model: simplified without mRNA dynamics
        # Solution: k_tl * (1 - exp(-k_m*t)) * exp(-beta*t)
        exp_km = np.exp(-k_m * dt)
        exp_beta = np.exp(-beta * dt)

        f[idx_after] = k_tl * (1 - exp_km) * exp_beta

        return f + offset

    def estimate_initial_params(self, t: np.ndarray, y: np.ndarray) -> dict[str, float]:
        """
        Estimate initial parameters from data.

        Args:
            t: Time points
            y: Fluorescence values

        Returns:
            Dictionary of estimated initial parameters
        """
        params = self.default_values.copy()

        # Estimate offset as minimum value
        params["offset"] = float(np.min(y))

        # Estimate t0 as time when signal starts increasing
        y_smooth = np.convolve(y, np.ones(3) / 3, mode="same")
        dy = np.diff(y_smooth)
        onset_idx = np.argmax(dy > np.std(dy))
        params["t0"] = float(t[onset_idx]) if onset_idx > 0 else float(t[0])

        # Estimate k_tl from amplitude
        amplitude = float(np.max(y) - np.min(y))
        params["k_tl"] = amplitude * 0.5

        return params

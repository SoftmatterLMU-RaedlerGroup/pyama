"""
Three-stage gene expression maturation model.

Based on the model from doi:10.1016/j.nano.2019.102077
Models gene expression as: mRNA → immature protein → mature protein
"""

import numpy as np
from .base import ModelBase


class MaturationModel(ModelBase):
    """
    Three-stage maturation model for fluorescence protein expression.

    The model describes gene expression through three stages:
    1. mRNA production and degradation
    2. Translation to immature protein
    3. Maturation to fluorescent protein

    Parameters:
        t0: Onset time of gene expression
        k_tl: Translation rate constant
        k_m: Maturation rate constant
        beta: Protein degradation rate
        delta: mRNA degradation rate
        offset: Baseline fluorescence offset
    """

    # Default values from Table 1 of doi:10.1016/j.nano.2019.102077
    _DEFAULT_VALUES = {
        "t0": 2.0,
        "k_tl": 1000.0,
        "k_m": 1.28,
        "beta": 5.22e-3,
        "delta": 0.01,
        "offset": 0.0,
    }

    # Parameter bounds
    _DEFAULT_BOUNDS = {
        "t0": (0.0, 30.0),
        "k_tl": (1.0, 5e8),
        "k_m": (1e-5, 30.0),
        "beta": (1e-5, 10.0),
        "delta": (1e-5, 11.0),
        "offset": (-1000.0, 1000.0),
    }

    def __init__(self):
        super().__init__()

        # Initialize parameter definitions
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
            "delta": {
                "values": [self._DEFAULT_VALUES["delta"]],
                "min": self._DEFAULT_BOUNDS["delta"][0],
                "max": self._DEFAULT_BOUNDS["delta"][1],
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
        return ["t0", "k_tl", "k_m", "beta", "delta", "offset"]

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
        delta: float,
        offset: float = 0.0,
    ) -> np.ndarray:
        """
        Evaluate the three-stage maturation model.

        Args:
            t: Array of time points
            t0: Onset time of gene expression
            k_tl: Translation rate constant
            k_m: Maturation rate constant
            beta: Protein degradation rate
            delta: mRNA degradation rate
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

        # Analytical solution of the ODE system
        bmd = beta - delta

        # Handle special case where beta ≈ delta
        if np.abs(bmd) < 1e-10:
            # Use L'Hôpital's rule limit
            f1 = dt * np.exp(-beta * dt) / (beta + k_m)
            f2 = -dt * np.exp(-beta * dt)
            f3 = k_m * dt * np.exp(-beta * dt) / (beta + k_m)
        else:
            f1 = np.exp(-(beta + k_m) * dt) / (bmd + k_m)
            f2 = -np.exp(-beta * dt) / bmd
            f3 = k_m / bmd / (bmd + k_m) * np.exp(-delta * dt)

        f[idx_after] = k_tl * (f1 + f2 + f3)

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
        y_smooth = np.convolve(y, np.ones(3) / 3, mode="same")  # Simple smoothing
        dy = np.diff(y_smooth)
        onset_idx = np.argmax(dy > np.std(dy))
        params["t0"] = float(t[onset_idx]) if onset_idx > 0 else float(t[0])

        # Estimate k_tl from amplitude
        amplitude = float(np.max(y) - np.min(y))
        params["k_tl"] = amplitude * 0.3  # Rough estimate

        return params

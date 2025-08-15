"""
Trivial exponential model for fluorescence traces.

Simple single exponential model for basic fitting.
"""

import numpy as np
from .base import ModelBase


class TrivialModel(ModelBase):
    """
    Simple exponential model for fluorescence traces.

    Models fluorescence as exponential growth/decay with onset time.

    Parameters:
        t0: Onset time
        amplitude: Maximum amplitude
        rate: Growth/decay rate constant
        offset: Baseline fluorescence offset
    """

    _DEFAULT_VALUES = {"t0": 2.0, "amplitude": 1000.0, "rate": 0.1, "offset": 0.0}

    _DEFAULT_BOUNDS = {
        "t0": (0.0, 30.0),
        "amplitude": (1.0, 1e6),
        "rate": (-1.0, 1.0),
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
            "amplitude": {
                "values": [self._DEFAULT_VALUES["amplitude"]],
                "min": self._DEFAULT_BOUNDS["amplitude"][0],
                "max": self._DEFAULT_BOUNDS["amplitude"][1],
                "fixed": False,
            },
            "rate": {
                "values": [self._DEFAULT_VALUES["rate"]],
                "min": self._DEFAULT_BOUNDS["rate"][0],
                "max": self._DEFAULT_BOUNDS["rate"][1],
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
        return ["t0", "amplitude", "rate", "offset"]

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
        amplitude: float,
        rate: float,
        offset: float = 0.0,
    ) -> np.ndarray:
        """
        Evaluate the exponential model.

        Args:
            t: Array of time points
            t0: Onset time
            amplitude: Maximum amplitude
            rate: Growth/decay rate constant
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

        # Simple exponential model
        if rate >= 0:
            # Growth: A * (1 - exp(-rate*t))
            f[idx_after] = amplitude * (1 - np.exp(-rate * dt))
        else:
            # Decay: A * exp(rate*t)
            f[idx_after] = amplitude * np.exp(rate * dt)

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

        # Estimate amplitude from range
        params["amplitude"] = float(np.max(y) - np.min(y))

        # Estimate t0 as time when signal starts increasing
        y_smooth = np.convolve(y, np.ones(3) / 3, mode="same")
        dy = np.diff(y_smooth)
        onset_idx = np.argmax(dy > np.std(dy))
        params["t0"] = float(t[onset_idx]) if onset_idx > 0 else float(t[0])

        # Estimate rate from data trend
        if len(y) > 1:
            final_val = np.mean(y[-3:])  # Average of last few points
            initial_val = np.mean(y[:3])  # Average of first few points
            if final_val > initial_val:
                params["rate"] = 0.1  # Growth
            else:
                params["rate"] = -0.1  # Decay

        return params

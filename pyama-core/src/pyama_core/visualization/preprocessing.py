"""
Preprocessing helpers for visualization (pure Python, Qt-free).
"""

import numpy as np


class VisualizationPreprocessingService:
    """Service for preprocessing image data for visualization."""

    def preprocess(self, data: np.ndarray, dtype: str) -> np.ndarray:
        """Preprocess image data based on data type.

        Args:
            data: Raw image data array
            dtype: Data type identifier

        Returns:
            Preprocessed image data array
        """
        if dtype.startswith("seg"):
            return data.astype(np.uint8)
        if data.ndim == 3:
            return self._normalize_stack(data)
        return self._normalize_frame(data)

    def _normalize_stack(self, stack: np.ndarray) -> np.ndarray:
        """Normalize an image stack with a consistent scale across all frames.

        Args:
            stack: Image stack to normalize (T, H, W)

        Returns:
            Normalized stack with uint8 data type
        """
        if stack.dtype == np.uint8:
            return stack

        f = stack.astype(np.float32)
        p1, p99 = np.percentile(f, 1), np.percentile(f, 99)

        if p99 <= p1:
            p1, p99 = float(f.min()), float(f.max())

        if p99 <= p1:
            return np.zeros_like(f, dtype=np.uint8)

        norm = np.clip((f - p1) / (p99 - p1), 0, 1)
        return (norm * 255).astype(np.uint8)

    def _normalize_frame(self, frame: np.ndarray) -> np.ndarray:
        """Normalize a single frame to uint8 range using percentile stretching."""
        if frame.dtype == np.uint8:
            return frame

        f = frame.astype(np.float32)
        p1, p99 = np.percentile(f, 1), np.percentile(f, 99)

        if p99 <= p1:
            p1, p99 = float(f.min()), float(f.max())

        if p99 <= p1:
            return np.zeros_like(f, dtype=np.uint8)

        norm = np.clip((f - p1) / (p99 - p1), 0, 1)
        return (norm * 255).astype(np.uint8)

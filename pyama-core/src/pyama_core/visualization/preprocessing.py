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
            return self._normalize_segmentation(data)
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

    def _normalize_segmentation(self, data: np.ndarray) -> np.ndarray:
        """Normalize segmentation data to uint8 range.

        For binary segmentation (0, 1), scales to (0, 255) so foreground is visible.
        For labeled segmentation, scales proportionally to [0, 255] based on max label.

        Args:
            data: Segmentation data array (binary or labeled)

        Returns:
            Normalized segmentation data as uint8
        """
        if data.dtype == np.uint8:
            # Check if already in full range
            if data.max() > 1:
                return data  # Already scaled
            # Binary data in uint8 (0, 1) - scale to full range
            return (data * 255).astype(np.uint8)

        # Convert to float for processing
        f = data.astype(np.float32)
        data_min = float(f.min())
        data_max = float(f.max())

        # Handle edge cases
        if data_max <= data_min:
            return np.zeros_like(f, dtype=np.uint8)

        # Scale to [0, 255] preserving relative values
        if data_max <= 1:
            # Binary data (0, 1) - scale to full range
            norm = f * 255
        else:
            # Labeled data - scale proportionally
            norm = (f - data_min) / (data_max - data_min) * 255

        return np.clip(norm, 0, 255).astype(np.uint8)

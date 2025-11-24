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
        For 3D stacks, scaling is computed across all frames to ensure consistent scale.

        Args:
            data: Segmentation data array (binary or labeled), can be 2D or 3D

        Returns:
            Normalized segmentation data as uint8
        """
        # Convert to float for processing
        f = data.astype(np.float32)
        
        # Compute min/max across entire stack (all frames) for consistent scaling
        data_min = float(f.min())
        data_max = float(f.max())

        # Handle edge cases
        if data_max <= data_min:
            return np.zeros_like(f, dtype=np.uint8)

        # Check if already normalized to full uint8 range (for cached data)
        # Only skip normalization if data is uint8 and already uses full range
        if data.dtype == np.uint8 and data_max >= 250:
            # Already normalized to full range, return as-is
            return data

        # Scale to [0, 255] preserving relative values
        # Use stack-wide min/max so all frames share the same scale
        if data_max <= 1:
            # Binary data (0, 1) - scale to full range
            norm = f * 255
        else:
            # Labeled data - scale proportionally to use full uint8 range
            # Scale computed across entire stack ensures consistent visualization
            norm = (f - data_min) / (data_max - data_min) * 255

        return np.clip(norm, 0, 255).astype(np.uint8)

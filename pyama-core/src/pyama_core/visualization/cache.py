"""
Caching helpers for visualization preprocessing (pure Python, Qt-free).
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from pyama_core.visualization.preprocessing import VisualizationPreprocessingService


@dataclass
class CachedStack:
    """Metadata for a cached, normalized stack."""

    path: Path
    shape: tuple[int, ...]
    n_frames: int
    vmin: int = 0
    vmax: int = 255


class VisualizationCache:
    """Cache manager for normalized uint8 stacks."""

    def __init__(self, cache_root: Path | None = None) -> None:
        """
        Args:
            cache_root: Optional root directory to store cached stacks. If None,
                caches alongside the source file.
        """
        self._cache_root = cache_root
        self._preprocessor = VisualizationPreprocessingService()

    def _resolve_cache_path(self, source_path: Path, channel_id: str) -> Path:
        """Compute cache path for a source stack."""
        base_dir = (
            self._cache_root
            if self._cache_root is not None
            else source_path.parent
        )
        base_dir.mkdir(parents=True, exist_ok=True)
        stem = source_path.stem
        suffix = source_path.suffix or ".npy"
        cache_name = f"{stem}_{channel_id}_uint8{suffix}"
        return base_dir / cache_name

    def get_or_build_uint8(
        self,
        source_path: Path,
        channel_id: str,
        *,
        force_rebuild: bool = False,
    ) -> CachedStack:
        """Return cached normalized stack, building it if missing."""
        cache_path = self._resolve_cache_path(source_path, channel_id)

        if cache_path.exists() and not force_rebuild:
            stack = np.load(cache_path)
            return CachedStack(
                path=cache_path,
                shape=tuple(stack.shape),
                n_frames=stack.shape[0] if stack.ndim == 3 else 1,
            )

        raw = np.load(source_path)
        processed = self._preprocessor.preprocess(raw, channel_id)
        np.save(cache_path, processed)

        return CachedStack(
            path=cache_path,
            shape=tuple(processed.shape),
            n_frames=processed.shape[0] if processed.ndim == 3 else 1,
        )

    def load_frame(self, cached_path: Path, frame: int) -> np.ndarray:
        """Load a single frame from a cached stack."""
        stack = np.load(cached_path)
        if stack.ndim == 3:
            return stack[frame]
        return stack

    def load_slice(self, cached_path: Path, start: int, end: int) -> np.ndarray:
        """Load a slice of frames [start, end] (inclusive) from a cached stack."""
        stack = np.load(cached_path)
        if stack.ndim == 3:
            return stack[start : end + 1]
        return stack

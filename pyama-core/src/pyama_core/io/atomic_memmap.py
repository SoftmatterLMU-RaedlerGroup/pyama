"""Simple memory-mapped array operations.

Provides a cross-platform wrapper for numpy memmap operations.
On Windows, uses direct writes due to file system limitations.
On Unix, can optionally use atomic temp file pattern.
"""

import logging
import platform
from pathlib import Path
from typing import Any
from numpy.lib.format import open_memmap

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


class AtomicMemmap:
    """Cross-platform memory-mapped array wrapper.

    On Windows: Uses direct writes (Windows file locking prevents atomic temp files)
    On Unix: Can use temp files for true atomicity (optional)
    """

    def __init__(
        self,
        path: Path,
        mode: str = "r",
        dtype: Any = None,
        shape: tuple[int, ...] | None = None,
        fortran_order: bool = False,
        version: tuple[int, int] = (1, 0),
    ) -> None:
        """Initialize atomic memmap wrapper."""
        self.path = Path(path)
        self.mode = mode
        self.dtype = dtype
        self.shape = shape
        self.fortran_order = fortran_order
        self.version = version
        self._memmap = None

        # Validate parameters for write modes
        if mode in ("w", "w+") and (shape is None or dtype is None):
            raise ValueError("shape and dtype are required for write modes")

    def __enter__(self):
        """Context manager entry - create/open the memmap."""
        if self.mode in ("w", "w+"):
            self._create_file()
        else:
            # Read modes - just open normally
            self._memmap = open_memmap(
                self.path,
                mode=self.mode,
                dtype=self.dtype,
                shape=self.shape,
                fortran_order=self.fortran_order,
                version=self.version,
            )
        return self._memmap

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensure proper cleanup."""
        if self._memmap is not None:
            try:
                self._memmap.flush()
            except Exception:
                pass
            try:
                self._memmap.close()
            except Exception:
                pass
            self._memmap = None

        # On Windows, direct writes were already atomic enough
        # On Unix, we could add temp file logic here if needed

        # Clean up on error
        if exc_type is not None and IS_WINDOWS:
            self._cleanup_on_error()

    def _create_file(self) -> None:
        """Create the memmap file using platform-appropriate method."""
        if IS_WINDOWS:
            self._create_windows()
        else:
            self._create_unix()

    def _create_windows(self) -> None:
        """Create memmap file on Windows with direct write."""
        # On Windows, atomic temp files don't work well due to file locking
        # Use direct writes with proper error handling instead
        if self.path.exists():
            logger.debug(f"File already exists, opening existing: {self.path}")
            self._memmap = open_memmap(
                self.path,
                mode=self.mode,
                dtype=self.dtype,
                shape=self.shape,
                fortran_order=self.fortran_order,
                version=self.version,
            )
        else:
            logger.debug(f"Creating new memmap file: {self.path}")
            try:
                self._memmap = open_memmap(
                    self.path,
                    mode=self.mode,
                    dtype=self.dtype,
                    shape=self.shape,
                    fortran_order=self.fortran_order,
                    version=self.version,
                )
            except Exception:
                # If creation fails, clean up any partial file
                if self.path.exists():
                    try:
                        self.path.unlink()
                    except Exception:
                        pass
                raise

    def _create_unix(self) -> None:
        """Create memmap file on Unix (could use atomic temp files here)."""
        # For now, use direct writes like Windows
        # Could be enhanced with temp file pattern if needed
        self._create_windows()

    def _cleanup_on_error(self) -> None:
        """Clean up partially written file on error."""
        try:
            if self.path.exists():
                self.path.unlink()
                logger.debug(f"Cleaned up partially written file: {self.path}")
        except Exception:
            pass


def atomic_open_memmap(
    path: Path,
    mode: str = "r",
    dtype: Any = None,
    shape: tuple[int, ...] | None = None,
    fortran_order: bool = False,
    version: tuple[int, int] = (1, 0),
) -> AtomicMemmap:
    """Open a memory-mapped array with platform-appropriate behavior.

    This provides a consistent interface while adapting to platform limitations.
    On Windows: Uses direct writes (atomic enough for most use cases)
    On Unix: Could use atomic temp files (future enhancement)

    Args:
        path: File path for the memmap
        mode: File mode ('r', 'r+', 'c', 'w', 'w+')
        dtype: Data type for the array
        shape: Shape of the array (required for write modes)
        fortran_order: Whether to use Fortran order
        version: NPY format version

    Returns:
        AtomicMemmap context manager
    """
    return AtomicMemmap(
        path=path,
        mode=mode,
        dtype=dtype,
        shape=shape,
        fortran_order=fortran_order,
        version=version,
    )

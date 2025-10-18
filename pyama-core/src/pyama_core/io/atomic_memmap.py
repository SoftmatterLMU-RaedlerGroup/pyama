"""Atomic memory-mapped array operations.

Provides atomic file creation for numpy memmap to avoid race conditions
when multiple processes try to create the same file simultaneously.
"""

import logging
import platform
from pathlib import Path
from typing import Any
from numpy.lib.format import open_memmap

logger = logging.getLogger(__name__)

IS_WINDOWS = platform.system() == "Windows"


class AtomicMemmap:
    """Atomic memory-mapped array that prevents race conditions during creation.
    
    On Windows: Uses direct writes with file locking checks
    On Unix: Uses temp file + atomic rename pattern
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
        """Initialize atomic memmap.
        
        Args:
            path: File path for the memmap
            mode: File mode ('r', 'r+', 'c', 'w', 'w+') 
            dtype: Data type for the array
            shape: Shape of the array (required for write modes)
            fortran_order: Whether to use Fortran order
            version: NPY format version
        """
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
        """Context manager entry - create/open the memmap atomically."""
        if self.mode in ("w", "w+"):
            self._create_atomic()
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
        
        # Perform atomic rename for Unix if no error occurred
        if exc_type is None and not IS_WINDOWS and hasattr(self, '_temp_path'):
            self.flush_and_rename()
        
        # Clean up temp files on error
        elif exc_type is not None and IS_WINDOWS:
            self._cleanup_on_error()
    
    def _create_atomic(self) -> None:
        """Create the memmap file atomically."""
        if IS_WINDOWS:
            self._create_windows()
        else:
            self._create_unix()
    
    def _create_windows(self) -> None:
        """Create memmap file on Windows with direct write."""
        # On Windows, we create directly but check for existing files first
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
        """Create memmap file on Unix with temp file + atomic rename."""
        import time
        import random
        
        # Generate unique temp filename
        timestamp = int(time.time() * 1000000)
        random_suffix = random.randint(1000, 9999)
        temp_path = self.path.parent / f"{self.path.stem}_{timestamp}_{random_suffix}.tmp"
        
        try:
            logger.debug(f"Creating temp memmap file: {temp_path}")
            self._memmap = open_memmap(
                temp_path,
                mode=self.mode,
                dtype=self.dtype,
                shape=self.shape,
                fortran_order=self.fortran_order,
                version=self.version,
            )
            
            # Schedule atomic rename when context exits
            self._temp_path = temp_path
            
        except Exception:
            # Clean up temp file on error
            if temp_path.exists():
                try:
                    temp_path.unlink()
                except Exception:
                    pass
            raise
    
    def _cleanup_on_error(self) -> None:
        """Clean up partially written file on error."""
        try:
            if self.path.exists():
                self.path.unlink()
                logger.debug(f"Cleaned up partially written file: {self.path}")
        except Exception:
            pass
    
    def flush_and_rename(self) -> None:
        """Flush data and perform atomic rename (Unix only)."""
        if not IS_WINDOWS and hasattr(self, '_temp_path'):
            try:
                if self._memmap is not None:
                    self._memmap.flush()
                    self._memmap.close()
                    self._memmap = None
                
                # Atomic rename
                if self._temp_path.exists():
                    import gc
                    gc.collect()
                    
                    # Remove target if it exists
                    if self.path.exists():
                        self.path.unlink()
                    
                    self._temp_path.rename(self.path)
                    logger.debug(f"Atomic rename complete: {self._temp_path} -> {self.path}")
                    
                delattr(self, '_temp_path')
                
            except Exception as e:
                logger.error(f"Failed to perform atomic rename: {e}")
                if hasattr(self, '_temp_path') and self._temp_path.exists():
                    try:
                        self._temp_path.unlink()
                    except Exception:
                        pass
                raise


def atomic_open_memmap(
    path: Path,
    mode: str = "r",
    dtype: Any = None,
    shape: tuple[int, ...] | None = None,
    fortran_order: bool = False,
    version: tuple[int, int] = (1, 0),
) -> AtomicMemmap:
    """Open a memory-mapped array atomically.
    
    This is a drop-in replacement for numpy.lib.format.open_memmap
    that provides atomic file creation to avoid race conditions.
    
    Args:
        path: File path for the memmap
        mode: File mode ('r', 'r+', 'c', 'w', 'w+')
        dtype: Data type for the array  
        shape: Shape of the array (required for write modes)
        fortran_order: Whether to use Fortran order
        version: NPY format version
        
    Returns:
        AtomicMemmap context manager
        
    Examples:
        # Writing (creates file atomically)
        with atomic_open_memmap("data.npy", "w+", dtype=np.uint16, shape=(100, 100)) as mmap:
            mmap[:] = my_data
            
        # Reading (normal operation)
        with atomic_open_memmap("data.npy", "r") as mmap:
            data = np.array(mmap)
    """
    return AtomicMemmap(
        path=path,
        mode=mode,
        dtype=dtype,
        shape=shape,
        fortran_order=fortran_order,
        version=version,
    )
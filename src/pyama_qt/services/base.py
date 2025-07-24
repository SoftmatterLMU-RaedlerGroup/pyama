"""
Base processing service classes for PyAMA-Qt microscopy image analysis.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
from PySide6.QtCore import QObject, Signal
from nd2reader import ND2Reader


class QObjectMeta(type(QObject), type(ABC)):
    """Metaclass that combines QObject and ABC metaclasses."""
    pass


class ProcessingService(QObject, ABC, metaclass=QObjectMeta):
    """Base class for all processing services with FOV-by-FOV processing pattern."""
    
    progress_updated = Signal(int)  # Progress percentage (0-100)
    status_updated = Signal(str)    # Status message
    step_completed = Signal(str)    # Step name when completed
    error_occurred = Signal(str)    # Error message
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        
    @abstractmethod
    def process_fov(self, nd2_path: str, fov_index: int, data_info: Dict[str, Any], 
                   output_dir: Path, params: Dict[str, Any]) -> bool:
        """
        Process a single field of view.
        
        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index to process
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def get_step_name(self) -> str:
        """Return the name of this processing step."""
        pass
    
    def process_all_fovs(self, nd2_path: str, data_info: Dict[str, Any], 
                        output_dir: Path, params: Dict[str, Any]) -> bool:
        """
        Process all fields of view in the ND2 file.
        
        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            
        Returns:
            bool: True if all FOVs processed successfully
        """
        try:
            self.status_updated.emit(f"Starting {self.get_step_name()}")
            
            n_fov = data_info['metadata']['n_fov']
            
            for fov_idx in range(n_fov):
                if self._is_cancelled:
                    self.status_updated.emit(f"{self.get_step_name()} cancelled")
                    return False
                    
                self.status_updated.emit(f"Processing FOV {fov_idx + 1}/{n_fov}")
                
                success = self.process_fov(nd2_path, fov_idx, data_info, output_dir, params)
                if not success:
                    error_msg = f"Failed to process FOV {fov_idx} in {self.get_step_name()}"
                    self.error_occurred.emit(error_msg)
                    return False
                
                # Update progress
                progress = int((fov_idx + 1) / n_fov * 100)
                self.progress_updated.emit(progress)
            
            self.status_updated.emit(f"{self.get_step_name()} completed successfully")
            self.step_completed.emit(self.get_step_name())
            return True
            
        except Exception as e:
            error_msg = f"Error in {self.get_step_name()}: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False
    
    def cancel(self):
        """Cancel the current processing operation."""
        self._is_cancelled = True
        self.status_updated.emit(f"Cancelling {self.get_step_name()}...")


class BaseProcessingService(ProcessingService):
    """Concrete base implementation with common utilities."""
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
    
    def create_memmap_array(self, shape: tuple, dtype: np.dtype, output_path: Path) -> np.memmap:
        """
        Create a memory-mapped numpy array for efficient large file handling.
        
        Args:
            shape: Array shape (e.g., (n_frames, height, width))
            dtype: Data type for the array
            output_path: Path where the memmap file will be saved
            
        Returns:
            np.memmap: Memory-mapped array
        """
        return np.memmap(output_path, dtype=dtype, mode='w+', shape=shape)
    
    def load_fov_frames(self, nd2_path: str, fov_index: int, channel_index: int, 
                       n_frames: int) -> np.ndarray:
        """
        Load all frames for a specific FOV and channel.
        
        Args:
            nd2_path: Path to ND2 file
            fov_index: Field of view index
            channel_index: Channel index
            n_frames: Number of frames to load
            
        Returns:
            np.ndarray: Array with shape (n_frames, height, width)
        """
        frames = []
        with ND2Reader(nd2_path) as images:
            for frame_idx in range(n_frames):
                # ND2Reader indexing: images[t, c, v, z, y, x]
                frame = images[frame_idx, channel_index, fov_index, 0]  # Assuming z=0
                frames.append(frame)
        
        return np.array(frames)
    
    def get_output_filename(self, base_name: str, fov_index: int, suffix: str) -> str:
        """
        Generate standardized output filename.
        
        Args:
            base_name: Base filename from ND2 file
            fov_index: Field of view index
            suffix: Suffix to append (e.g., 'binarized', 'phase_contrast')
            
        Returns:
            str: Generated filename
        """
        return f"{base_name}_fov{fov_index:02d}_{suffix}.npz"
"""
Worker class for asynchronous preprocessing of FOV data.
"""
import numpy as np
from PySide6.QtCore import QObject, Signal, QThread
from pathlib import Path
import logging

from ....core.data_loading import load_image_data


class PreprocessingWorker(QObject):
    """Worker class for preprocessing FOV data in a background thread."""
    
    # Signals for communication with the main thread
    progress_updated = Signal(str)  # Message about current progress
    fov_data_loaded = Signal(dict)  # Emitted when FOV data is loaded and preprocessed
    finished = Signal()  # Emitted when all processing is complete
    error_occurred = Signal(str)  # Emitted when an error occurs
    
    def __init__(self, project_data: dict, fov_idx: int):
        """
        Initialize the worker.
        
        Args:
            project_data: Project data dictionary
            fov_idx: Index of the FOV to process
        """
        super().__init__()
        self.project_data = project_data
        self.fov_idx = fov_idx
        self.current_images = {}
        self.logger = logging.getLogger(__name__)
        
    def process_fov_data(self):
        """Process FOV data in the background thread."""
        try:
            self.progress_updated.emit(f"Loading data for FOV {self.fov_idx:04d}...")
            
            if self.fov_idx not in self.project_data['fov_data']:
                self.error_occurred.emit(f"FOV {self.fov_idx} not found in project data")
                return
                
            fov_data = self.project_data['fov_data'][self.fov_idx]
            image_types = [k for k in fov_data.keys() if k != 'traces']
            
            self.logger.info(f"Preloading {len(image_types)} data types for FOV {self.fov_idx}")
            self.progress_updated.emit(f"Preloading {len(image_types)} data types for FOV {self.fov_idx}...")
            
            # Load and preprocess all image data
            for i, data_type in enumerate(sorted(image_types)):
                try:
                    self.progress_updated.emit(f"Loading {data_type} ({i+1}/{len(image_types)})...")
                    image_path = fov_data[data_type]
                    
                    # Use memory mapping for efficient loading of large files
                    if image_path.suffix.lower() == '.npy':
                        image_data = load_image_data(image_path, mmap_mode='r')
                    elif image_path.suffix.lower() == '.npz':
                        # For NPZ files, we still need to load the data but can do it once
                        image_data = load_image_data(image_path)
                    else:
                        # For other formats, use the existing loader
                        image_data = load_image_data(image_path)
                    
                    # Preprocess data for visualization (normalize to uint8)
                    self.progress_updated.emit(f"Preprocessing {data_type} ({i+1}/{len(image_types)})...")
                    processed_data = self._preprocess_for_visualization(image_data, data_type)
                    
                    self.current_images[(self.fov_idx, data_type)] = processed_data
                    self.logger.info(f"Preloaded and processed {data_type} data: shape {processed_data.shape}, dtype {processed_data.dtype}")
                    
                except Exception as e:
                    self.logger.error(f"Error preloading {data_type} data for FOV {self.fov_idx}: {e}")
                    # Continue with other data types even if one fails
                    continue
                    
            self.logger.info(f"Completed preloading data for FOV {self.fov_idx}")
            self.progress_updated.emit(f"Completed preloading data for FOV {self.fov_idx}")
            
            # Emit the loaded data
            result = {
                'fov_idx': self.fov_idx,
                'images': self.current_images
            }
            self.fov_data_loaded.emit(result)
            
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            self.finished.emit()
            
    def _preprocess_for_visualization(self, image_data: np.ndarray, data_type: str) -> np.ndarray:
        """
        Preprocess image data for visualization by normalizing to uint8.
        
        Args:
            image_data: Input image data
            data_type: Type of data (for special handling)
            
        Returns:
            Preprocessed image data as uint8
        """
        # Handle different data types
        if image_data.dtype == np.bool_ or image_data.dtype == bool or 'binarized' in data_type:
            # Binary image - convert to uint8 directly
            return (image_data * 255).astype(np.uint8)
        else:
            # For other data types, normalize to uint8
            # Calculate min/max for normalization
            data_min = np.nanmin(image_data)
            data_max = np.nanmax(image_data)
            
            # Avoid division by zero
            if data_max > data_min:
                # Normalize to 0-255 range
                normalized = ((image_data - data_min) / (data_max - data_min) * 255).astype(np.uint8)
            else:
                normalized = np.zeros_like(image_data, dtype=np.uint8)
                
            return normalized
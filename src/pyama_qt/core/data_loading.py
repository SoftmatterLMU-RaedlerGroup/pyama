"""
Core data loading utilities shared between processing and visualization apps.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing_extensions import TypedDict
import nd2


class ND2Metadata(TypedDict):
    """Type definition for essential ND2 metadata"""
    filepath: str          # Full path to ND2 file
    filename: str          # Just the filename
    n_frames: int          # Number of time points
    height: int            # Image height in pixels
    width: int             # Image width in pixels  
    n_fov: int             # Number of fields of view
    channels: list[str]    # Channel names
    n_channels: int        # Number of channels
    pixel_microns: float   # Pixel size in microns
    native_dtype: str      # Original data type from ND2


class ProcessingResults(TypedDict, total=False):
    """Type definition for processing results structure"""
    # Metadata
    project_path: Path
    nd2_file: str
    n_fov: int
    
    # Data paths by FOV
    fov_data: dict[int, dict[str, Path]]  # {fov_idx: {data_type: path}}


def get_nd2_frame(nd2_path: str | Path, fov: int, channel: int, frame: int) -> np.ndarray:
    """
    Get a single 2D frame from the ND2 file.
    
    Args:
        nd2_path: Path to ND2 file
        fov: Field of view index
        channel: Channel index
        frame: Time frame index
        
    Returns:
        2D numpy array of the requested frame
    """
    with nd2.ND2File(str(nd2_path)) as f:
        # Use dask for lazy loading to avoid memory issues
        dask_array = f.to_dask()
        
        # Build indexing based on the shape and sizes
        # The sizes dict tells us which dimensions exist
        indices = {}
        
        if 'T' in f.sizes:
            indices['T'] = frame
        if 'P' in f.sizes:
            indices['P'] = fov
        if 'C' in f.sizes:
            indices['C'] = channel
        if 'Z' in f.sizes:
            indices['Z'] = 0  # Default to first Z plane
        
        # Create the indexing tuple in the order of dimensions
        # The order should match the array shape
        index_list = []
        
        # Common dimension order in nd2 files: TPCZYX
        for dim in ['T', 'P', 'C', 'Z', 'Y', 'X']:
            if dim in f.sizes:
                if dim in indices:
                    index_list.append(indices[dim])
                elif dim in ['Y', 'X']:
                    # Keep all Y and X values (full 2D frame)
                    index_list.append(slice(None))
                else:
                    index_list.append(0)
        
        # Get the specific frame using dask indexing and compute to numpy
        result = dask_array[tuple(index_list)].compute()
        
        # Ensure we return a 2D array
        while result.ndim > 2:
            result = result[0]
        
        return result


def load_nd2_metadata(nd2_path: str | Path) -> ND2Metadata:
    """
    Load essential ND2 file metadata for processing and visualization.
    
    Args:
        nd2_path: Path to ND2 file
        
    Returns:
        Dictionary containing essential metadata only
    """
    try:
        nd2_path = Path(nd2_path)
        
        with nd2.ND2File(str(nd2_path)) as f:
            # Get essential metadata only
            metadata: ND2Metadata = {
                'filepath': str(nd2_path),
                'filename': nd2_path.name,
                
                # Core dimensions
                'n_frames': f.sizes.get('T', 1),
                'height': f.sizes.get('Y', 0),
                'width': f.sizes.get('X', 0),
                'n_fov': f.sizes.get('P', 1),
                
                # Channel info - extract channel names from Channel objects
                'channels': [ch.channel.name for ch in (f.metadata.channels or [])],
                'n_channels': f.sizes.get('C', 1),
                
                # Physical units
                'pixel_microns': f.voxel_size().x if f.voxel_size() else 1.0,
                
                # Data type
                'native_dtype': str(f.dtype),
            }
            
            return metadata
            
    except Exception as e:
        raise RuntimeError(f"Failed to load ND2 metadata: {str(e)}")


def discover_processing_results(output_dir: Path) -> ProcessingResults:
    """
    Discover and catalog processing results in an output directory.
    
    This function looks for processing output files based on naming patterns.
    
    Args:
        output_dir: Path to processing output directory
        
    Returns:
        ProcessingResults structure with paths to all data files
    """
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")
    
    return _discover_from_file_patterns(output_dir)




def _discover_from_file_patterns(output_dir: Path) -> ProcessingResults:
    """Discover results using file naming patterns (legacy method)."""
    # Find FOV directories
    fov_dirs = [d for d in output_dir.iterdir() if d.is_dir() and d.name.startswith('fov_')]
    
    if not fov_dirs:
        raise ValueError(f"No FOV directories found in {output_dir}")
    
    # Build catalog of available data
    fov_data = {}
    
    for fov_dir in sorted(fov_dirs):
        # Extract FOV index from directory name (e.g., fov_0001 -> 1)
        fov_idx = int(fov_dir.name.split('_')[1])
        
        # Find data files in this FOV directory
        data_files = {}
        
        for file_path in fov_dir.iterdir():
            if file_path.is_file():
                # Determine data type from filename
                if 'binarized' in file_path.name:
                    data_files['binarized'] = file_path
                elif 'phase_contrast' in file_path.name:
                    data_files['phase_contrast'] = file_path
                elif 'fluorescence_corrected' in file_path.name:
                    data_files['fluorescence_corrected'] = file_path
                elif 'fluorescence_raw' in file_path.name:
                    data_files['fluorescence_raw'] = file_path
                elif 'traces.csv' in file_path.name:
                    data_files['traces'] = file_path
        
        fov_data[fov_idx] = data_files
    
    # Try to find original ND2 file reference
    nd2_file = ""
    if fov_data:
        # Look for ND2 filename in any data file name
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            # Extract base name from filename pattern: basename_fov0000_suffix.ext
            parts = file_path.stem.split('_fov')
            if len(parts) > 0:
                nd2_file = parts[0] + '.nd2'
                break
    
    return ProcessingResults(
        project_path=output_dir,
        nd2_file=nd2_file,
        n_fov=len(fov_data),
        fov_data=fov_data
    )


def load_traces_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load cellular traces from CSV file.
    
    Args:
        csv_path: Path to traces CSV file
        
    Returns:
        DataFrame with trace data
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Traces file not found: {csv_path}")
    
    return pd.read_csv(csv_path)


def load_image_data(file_path: Path, mmap_mode: str | None = None) -> np.ndarray:
    """
    Load image data from file (NPZ or NPY).
    
    Args:
        file_path: Path to image data file
        mmap_mode: Memory mapping mode for NPY files (e.g., 'r' for read-only)
                    If None, loads the entire array into memory
        
    Returns:
        Image data array
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Image data file not found: {file_path}")
    
    # Handle both .npy and .npz files
    if file_path.suffix == '.npy':
        return np.load(file_path, mmap_mode=mmap_mode)
    elif file_path.suffix == '.npz':
        # NPZ files don't support memory mapping in the same way
        # Load normally but respect the mmap_mode for consistency in API
        with np.load(file_path) as data:
            return data['arr_0']
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}")


def get_fov_project_metadata(results: ProcessingResults, fov_idx: int) -> dict:
    """
    Get project metadata for a specific FOV.
    
    Args:
        results: ProcessingResults structure
        fov_idx: FOV index
        
    Returns:
        FOV project metadata dictionary or empty dict if not available
    """
    # No project files supported anymore, return empty dict
    return {}
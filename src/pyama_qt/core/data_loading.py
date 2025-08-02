"""
Core data loading utilities shared between processing and visualization apps.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing_extensions import TypedDict
from nd2reader import ND2Reader


class ProcessingResults(TypedDict, total=False):
    """Type definition for processing results structure"""
    # Metadata
    project_path: Path
    nd2_file: str
    n_fov: int
    
    # Data paths by FOV
    fov_data: dict[int, dict[str, Path]]  # {fov_idx: {data_type: path}}


def load_nd2_metadata(nd2_path: str | Path) -> dict[str, object]:
    """
    Load ND2 file metadata for both processing and visualization.
    
    Args:
        nd2_path: Path to ND2 file
        
    Returns:
        Dictionary containing metadata
    """
    try:
        with ND2Reader(str(nd2_path)) as images:
            # Get basic metadata
            img_metadata = images.metadata or {}
            
            metadata = {
                'filepath': str(nd2_path),
                'filename': Path(nd2_path).name,
                'sizes': dict(images.sizes),
                'channels': list(img_metadata.get('channels', [])),
                'date': img_metadata.get('date'),
                'experiment': img_metadata.get('experiment', {}),
                'fields_of_view': img_metadata.get('fields_of_view', []),
                'frames': img_metadata.get('frames', []),
                'height': img_metadata.get('height', images.sizes.get('y', 0)),
                'num_frames': img_metadata.get('num_frames', 0),
                'pixel_microns': img_metadata.get('pixel_microns', 0.0),
                'total_images_per_channel': img_metadata.get('total_images_per_channel', 0),
                'width': img_metadata.get('width', images.sizes.get('x', 0)),
                'z_levels': img_metadata.get('z_levels', []),
                'n_channels': images.sizes.get('c', 1),
                'n_frames': images.sizes.get('t', 1),
                'n_fov': images.sizes.get('v', len(img_metadata.get('fields_of_view', [0]))),
                'n_z_levels': images.sizes.get('z', len(img_metadata.get('z_levels', [0]))),
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


def load_image_data(npz_path: Path) -> np.ndarray:
    """
    Load image data from NPZ file.
    
    Args:
        npz_path: Path to NPZ file
        
    Returns:
        Image data array
    """
    if not npz_path.exists():
        raise FileNotFoundError(f"Image data file not found: {npz_path}")
    
    with np.load(npz_path) as data:
        return data['arr_0']


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
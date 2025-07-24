"""
Core data loading utilities shared between processing and visualization apps.
"""

import numpy as np
import pandas as pd
from pathlib import Path
from typing_extensions import TypedDict
from nd2reader import ND2Reader
from .project import (
    find_project_file, 
    load_project_file, 
    validate_project_files,
    find_master_project_file,
    load_master_project_file
)


class ProcessingResults(TypedDict, total=False):
    """Type definition for processing results structure"""
    # Metadata
    project_path: Path
    nd2_file: str
    n_fov: int
    
    # Data paths by FOV
    fov_data: dict[int, dict[str, Path]]  # {fov_idx: {data_type: path}}
    
    # Project file information (if available)
    has_project_file: bool
    has_master_project_file: bool
    project_metadata: dict  # Full project TOML data
    master_project_metadata: dict  # Master project TOML data (if available)
    processing_parameters: dict  # Parameters used for processing
    processing_status: str  # "completed", "failed", etc.
    
    # FOV navigation (from master project)
    fov_project_files: dict[int, Path]  # {fov_idx: path_to_fov_project_file}


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
    
    This function first looks for a master project file (pyama_master_project.toml)
    which organizes multiple FOV project files. If no master project file is found,
    it falls back to looking for a single project file or file naming patterns.
    
    Args:
        output_dir: Path to processing output directory
        
    Returns:
        ProcessingResults structure with paths to all data files
    """
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")
    
    # First, try to find and load a master project file
    master_project_file = find_master_project_file(output_dir)
    
    if master_project_file:
        return _discover_from_master_project_file(output_dir, master_project_file)
    
    # Fallback to single project file
    project_file = find_project_file(output_dir)
    
    if project_file:
        return _discover_from_project_file(output_dir, project_file)
    else:
        return _discover_from_file_patterns(output_dir)


def _discover_from_master_project_file(output_dir: Path, master_project_file: Path) -> ProcessingResults:
    """Discover results using master project file metadata."""
    try:
        master_data = load_master_project_file(master_project_file)
        
        # Build FOV data and project file mapping from master project
        fov_data = {}
        fov_project_files = {}
        
        for fov_key, fov_info in master_data["fovs"].items():
            fov_idx = fov_info["index"]
            fov_project_path = output_dir / fov_info["project_file"]
            
            # Only include FOVs that have project files
            if fov_project_path.exists():
                fov_project_files[fov_idx] = fov_project_path
                
                # Load individual FOV project file to get data file paths
                try:
                    fov_project_data = load_project_file(fov_project_path)
                    fov_dir = fov_project_path.parent
                    
                    data_files = {}
                    for key, value in fov_project_data["output"].items():
                        if key.startswith("fov_"):
                            for data_type, filename in value.items():
                                if data_type != "status":
                                    file_path = fov_dir / filename
                                    if file_path.exists():
                                        data_files[data_type] = file_path
                    
                    if data_files:
                        fov_data[fov_idx] = data_files
                        
                except Exception as e:
                    print(f"Warning: Could not load FOV project file {fov_project_path}: {e}")
                    continue
        
        return ProcessingResults(
            project_path=output_dir,
            nd2_file=master_data["input"]["filename"],
            n_fov=len(fov_data),
            fov_data=fov_data,
            has_project_file=True,  # Individual FOV project files exist
            has_master_project_file=True,
            project_metadata={},  # Individual FOV metadata loaded separately
            master_project_metadata=master_data,
            processing_parameters=master_data["processing"]["parameters"],
            processing_status=master_data["processing"]["status"],
            fov_project_files=fov_project_files
        )
        
    except Exception as e:
        # If master project file is corrupted, fall back to single project discovery
        print(f"Warning: Could not read master project file {master_project_file}, falling back: {e}")
        project_file = find_project_file(output_dir)
        if project_file:
            return _discover_from_project_file(output_dir, project_file)
        else:
            return _discover_from_file_patterns(output_dir)


def _discover_from_project_file(output_dir: Path, project_file: Path) -> ProcessingResults:
    """Discover results using project file metadata."""
    try:
        project_data = load_project_file(project_file)
        
        # Validate that referenced files actually exist
        file_validation = validate_project_files(project_data)
        
        # Build FOV data from project file
        fov_data = {}
        
        for key, value in project_data["output"].items():
            if key.startswith("fov_"):
                fov_idx = int(key.split("_")[1])
                fov_dir = output_dir / key
                
                data_files = {}
                for data_type, filename in value.items():
                    if data_type != "status":
                        file_path = fov_dir / filename
                        # Only include files that actually exist
                        if file_path.exists():
                            data_files[data_type] = file_path
                
                if data_files:  # Only include FOVs that have some data
                    fov_data[fov_idx] = data_files
        
        return ProcessingResults(
            project_path=output_dir,
            nd2_file=project_data["input"]["filename"],
            n_fov=len(fov_data),
            fov_data=fov_data,
            has_project_file=True,
            has_master_project_file=False,
            project_metadata=project_data,
            master_project_metadata={},
            processing_parameters=project_data["processing"]["parameters"],
            processing_status=project_data["processing"]["status"],
            fov_project_files={}
        )
        
    except Exception as e:
        # If project file is corrupted, fall back to pattern discovery
        print(f"Warning: Could not read project file {project_file}, falling back to pattern discovery: {e}")
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
        fov_data=fov_data,
        has_project_file=False,
        has_master_project_file=False,
        project_metadata={},
        master_project_metadata={},
        processing_parameters={},
        processing_status="unknown",
        fov_project_files={}
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
    if not results.get("has_master_project_file", False):
        return results.get("project_metadata", {})
    
    fov_project_files = results.get("fov_project_files", {})
    if fov_idx not in fov_project_files:
        return {}
    
    try:
        fov_project_path = fov_project_files[fov_idx]
        return load_project_file(fov_project_path)
    except Exception as e:
        print(f"Warning: Could not load FOV {fov_idx} project metadata: {e}")
        return {}
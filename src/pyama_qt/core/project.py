"""
Project file management for PyAMA-Qt processing results.

Handles creation and reading of TOML project files that contain metadata
about processing runs, making visualization much smarter.
"""

# Handle TOML imports for different Python versions
try:
    import tomllib  # Python 3.11+
except ImportError:
    import tomli as tomllib  # Python < 3.11

import tomli_w
from pathlib import Path
from datetime import datetime, timezone
from typing_extensions import TypedDict
import platform


def clean_dict_for_toml(d: dict) -> dict:
    """
    Clean a dictionary for TOML serialization by removing None values.
    
    TOML doesn't support None/null values, so we need to remove them
    or convert them to appropriate defaults.
    """
    cleaned = {}
    for key, value in d.items():
        if value is None:
            # Skip None values
            continue
        elif isinstance(value, dict):
            # Recursively clean nested dictionaries
            cleaned_value = clean_dict_for_toml(value)
            if cleaned_value:  # Only include non-empty dicts
                cleaned[key] = cleaned_value
        else:
            cleaned[key] = value
    return cleaned


def write_toml_with_none_removal(file_path: Path, data: dict) -> None:
    """
    Write data to TOML file after removing None values.
    
    This is a utility function that cleans the data dictionary by removing
    all None values (which are not TOML serializable) and then writes the
    cleaned data to the specified TOML file.
    
    Args:
        file_path: Path to the TOML file to write
        data: Dictionary to write to TOML
    """
    cleaned_data = clean_dict_for_toml(data)
    with open(file_path, "wb") as f:
        tomli_w.dump(cleaned_data, f)


class ProjectMetadata(TypedDict, total=False):
    """Type definition for project metadata structure"""
    # Project info
    name: str
    created: str  # ISO timestamp
    pyama_version: str
    python_version: str
    platform: str
    description: str
    
    # Input file info
    input: dict
    
    # Processing info
    processing: dict
    
    # Output info  
    output: dict
    
    # Statistics
    statistics: dict


class MasterProjectMetadata(TypedDict, total=False):
    """Type definition for master project metadata structure"""
    # Master project info
    name: str
    created: str  # ISO timestamp
    pyama_version: str
    python_version: str
    platform: str
    description: str
    
    # Input ND2 file info
    input: dict
    
    # Master processing info
    processing: dict
    
    # FOV organization
    fovs: dict  # Maps FOV index to FOV project file path
    
    # Statistics across all FOVs
    statistics: dict


def create_project_file(
    output_dir: Path,
    nd2_path: str,
    data_info: dict,
    processing_params: dict,
    project_name: str = None
) -> Path:
    """
    Create a project TOML file with processing metadata.
    
    Args:
        output_dir: Directory where results are stored
        nd2_path: Path to original ND2 file
        data_info: Metadata from ND2 loading
        processing_params: Parameters used for processing
        project_name: Optional project name (defaults to ND2 filename)
        
    Returns:
        Path to created project file
    """
    if project_name is None:
        project_name = Path(nd2_path).stem
        
    now = datetime.now(timezone.utc)
    
    # Build project metadata
    project_data = {
        "project": {
            "name": project_name,
            "created": now.isoformat(),
            "pyama_version": "0.1.0",  # TODO: Get from package metadata
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "description": f"PyAMA-Qt processing results for {Path(nd2_path).name}"
        },
        
        "input": {
            "nd2_file": str(nd2_path),
            "filename": data_info["filename"],
            "channels": data_info["channels"],
            "pc_channel": data_info.get("pc_channel"),
            "fl_channel": data_info.get("fl_channel"),
            "pc_channel_name": data_info.get("pc_channel_name"),
            "fl_channel_name": data_info.get("fl_channel_name"),
            
            "metadata": {
                "n_fov": data_info["metadata"]["n_fov"],
                "n_frames": data_info["metadata"]["n_frames"], 
                "n_channels": data_info["metadata"]["n_channels"],
                "width": data_info["metadata"]["width"],
                "height": data_info["metadata"]["height"],
                "pixel_microns": data_info["metadata"]["pixel_microns"],
                "date": str(data_info["metadata"].get("date", "")),
            }
        },
        
        "processing": {
            "status": "started",
            "started": now.isoformat(),
            "completed": None,
            "duration_seconds": None,
            
            "parameters": {
                "mask_size": processing_params.get("mask_size", 3),
                "div_horiz": processing_params.get("div_horiz", 7),
                "div_vert": processing_params.get("div_vert", 5),
                "min_trace_length": processing_params.get("min_trace_length", 3),
            },
            
            "steps": {
                "binarization": {"status": "pending"},
                "background_correction": {"status": "pending"},
                "trace_extraction": {"status": "pending"},
            }
        },
        
        "output": {
            "directory": str(output_dir),
            "fov_count": data_info["metadata"]["n_fov"],
        },
        
        "statistics": {
            "total_cells_tracked": None,
            "average_trace_length": None,
            "processing_errors": 0,
        }
    }
    
    # Initialize FOV sections
    n_fov = data_info["metadata"]["n_fov"]
    base_name = data_info["filename"].replace(".nd2", "")
    
    for fov_idx in range(n_fov):
        fov_key = f"fov_{fov_idx:04d}"
        project_data["output"][fov_key] = {
            "binarized": f"{base_name}_fov{fov_idx:04d}_binarized.npz",
            "phase_contrast": f"{base_name}_fov{fov_idx:04d}_phase_contrast.npz", 
            "fluorescence_corrected": f"{base_name}_fov{fov_idx:04d}_fluorescence_corrected.npz",
            "traces": f"{base_name}_fov{fov_idx:04d}_traces.csv",
            "status": "pending"
        }
    
    # Clean data for TOML serialization
    project_data = clean_dict_for_toml(project_data)
    
    # Write project file
    project_file_path = output_dir / "pyama_project.toml"
    write_toml_with_none_removal(project_file_path, project_data)
        
    return project_file_path


def update_project_step_status(
    project_file: Path,
    step_name: str,
    status: str,
    duration_seconds: float = None
):
    """
    Update the status of a processing step in the project file.
    
    Args:
        project_file: Path to project TOML file
        step_name: Name of processing step
        status: New status ("completed", "failed", etc.)
        duration_seconds: Optional duration for the step
    """
    if not project_file.exists():
        return
        
    # Read current project data
    with open(project_file, "rb") as f:
        project_data = tomllib.load(f)
    
    # Update step status
    if step_name in project_data["processing"]["steps"]:
        project_data["processing"]["steps"][step_name]["status"] = status
        if duration_seconds is not None:
            project_data["processing"]["steps"][step_name]["duration_seconds"] = duration_seconds
    
    # Clean and write back to file
    project_data = clean_dict_for_toml(project_data)
    write_toml_with_none_removal(project_file, project_data)


def update_project_fov_status(
    project_file: Path,
    fov_idx: int,
    status: str
):
    """
    Update the status of a specific FOV in the project file.
    
    Args:
        project_file: Path to project TOML file
        fov_idx: FOV index
        status: New status ("completed", "failed", etc.)
    """
    if not project_file.exists():
        return
        
    # Read current project data
    with open(project_file, "rb") as f:
        project_data = tomllib.load(f)
    
    # Update FOV status
    fov_key = f"fov_{fov_idx:04d}"
    if fov_key in project_data["output"]:
        project_data["output"][fov_key]["status"] = status
    
    # Clean and write back to file
    project_data = clean_dict_for_toml(project_data)
    write_toml_with_none_removal(project_file, project_data)


def finalize_project_file(
    project_file: Path,
    success: bool,
    statistics: dict = None
):
    """
    Finalize project file after processing completion.
    
    Args:
        project_file: Path to project TOML file
        success: Whether processing completed successfully
        statistics: Optional processing statistics
    """
    if not project_file.exists():
        return
        
    # Read current project data
    with open(project_file, "rb") as f:
        project_data = tomllib.load(f)
    
    now = datetime.now(timezone.utc)
    started_time = datetime.fromisoformat(project_data["processing"]["started"])
    duration = (now - started_time).total_seconds()
    
    # Update processing status
    project_data["processing"]["status"] = "completed" if success else "failed"
    project_data["processing"]["completed"] = now.isoformat()
    project_data["processing"]["duration_seconds"] = duration
    
    # Update statistics if provided
    if statistics:
        project_data["statistics"].update(statistics)
    
    # Clean and write back to file
    project_data = clean_dict_for_toml(project_data)
    write_toml_with_none_removal(project_file, project_data)


def load_project_file(project_file: Path) -> dict:
    """
    Load project metadata from TOML file.
    
    Args:
        project_file: Path to project TOML file
        
    Returns:
        Project metadata dictionary
    """
    if not project_file.exists():
        raise FileNotFoundError(f"Project file not found: {project_file}")
        
    with open(project_file, "rb") as f:
        return tomllib.load(f)


def find_project_file(directory: Path) -> Path | None:
    """
    Find a project file in the given directory.
    
    Args:
        directory: Directory to search in
        
    Returns:
        Path to project file or None if not found
    """
    project_file = directory / "pyama_project.toml"
    return project_file if project_file.exists() else None


def validate_project_files(project_data: dict) -> dict[str, bool]:
    """
    Validate that all files referenced in project exist.
    
    Args:
        project_data: Project metadata dictionary
        
    Returns:
        Dictionary mapping file paths to existence status
    """
    validation_results = {}
    output_dir = Path(project_data["output"]["directory"])
    
    # Check input ND2 file
    nd2_path = Path(project_data["input"]["nd2_file"])
    validation_results["nd2_file"] = nd2_path.exists()
    
    # Check output files for each FOV
    for key, value in project_data["output"].items():
        if key.startswith("fov_"):
            fov_dir = output_dir / key
            for data_type, filename in value.items():
                if data_type != "status":
                    file_path = fov_dir / filename
                    validation_results[str(file_path)] = file_path.exists()
    
    return validation_results


def create_master_project_file(
    output_dir: Path,
    nd2_path: str,
    data_info: dict,
    processing_params: dict,
    project_name: str = None
) -> Path:
    """
    Create a master project file that organizes FOV-level project files.
    
    Args:
        output_dir: Directory where results are stored
        nd2_path: Path to original ND2 file
        data_info: Metadata from ND2 loading
        processing_params: Parameters used for processing
        project_name: Optional project name (defaults to ND2 filename)
        
    Returns:
        Path to created master project file
    """
    if project_name is None:
        project_name = Path(nd2_path).stem
        
    now = datetime.now(timezone.utc)
    
    # Build master project metadata
    master_data = {
        "project": {
            "name": project_name,
            "created": now.isoformat(),
            "pyama_version": "0.1.0",  # TODO: Get from package metadata
            "python_version": platform.python_version(),
            "platform": platform.system(),
            "description": f"PyAMA-Qt master project for {Path(nd2_path).name}"
        },
        
        "input": {
            "nd2_file": str(nd2_path),
            "filename": data_info["filename"],
            "channels": data_info["channels"],
            "pc_channel": data_info.get("pc_channel"),
            "fl_channel": data_info.get("fl_channel"),
            "pc_channel_name": data_info.get("pc_channel_name"),
            "fl_channel_name": data_info.get("fl_channel_name"),
            
            "metadata": {
                "n_fov": data_info["metadata"]["n_fov"],
                "n_frames": data_info["metadata"]["n_frames"], 
                "n_channels": data_info["metadata"]["n_channels"],
                "width": data_info["metadata"]["width"],
                "height": data_info["metadata"]["height"],
                "pixel_microns": data_info["metadata"]["pixel_microns"],
                "date": str(data_info["metadata"].get("date", "")),
            }
        },
        
        "processing": {
            "status": "started",
            "started": now.isoformat(),
            "completed": None,
            "duration_seconds": None,
            
            "parameters": {
                "mask_size": processing_params.get("mask_size", 3),
                "div_horiz": processing_params.get("div_horiz", 7),
                "div_vert": processing_params.get("div_vert", 5),
                "min_trace_length": processing_params.get("min_trace_length", 3),
            },
            
            "total_fovs": data_info["metadata"]["n_fov"],
            "completed_fovs": 0,
            "failed_fovs": 0,
        },
        
        "fovs": {},
        
        "statistics": {
            "total_cells_tracked": None,
            "average_trace_length": None,
            "processing_errors": 0,
            "total_processing_time": None,
        }
    }
    
    # Initialize FOV entries - each FOV gets its own project file
    n_fov = data_info["metadata"]["n_fov"]
    
    for fov_idx in range(n_fov):
        fov_key = f"fov_{fov_idx:04d}"
        fov_project_file = f"fov_{fov_idx:04d}/pyama_project.toml"
        
        master_data["fovs"][fov_key] = {
            "index": fov_idx,
            "project_file": fov_project_file,
            "status": "pending",
            "started": None,
            "completed": None,
            "duration_seconds": None,
        }
    
    # Clean data for TOML serialization
    master_data = clean_dict_for_toml(master_data)
    
    # Write master project file
    master_project_file = output_dir / "pyama_master_project.toml"
    write_toml_with_none_removal(master_project_file, master_data)
        
    return master_project_file


def update_master_project_fov_status(
    master_project_file: Path,
    fov_idx: int,
    status: str,
    started: datetime = None,
    completed: datetime = None,
    duration_seconds: float = None
):
    """
    Update the status of a specific FOV in the master project file.
    
    Args:
        master_project_file: Path to master project TOML file
        fov_idx: FOV index
        status: New status ("started", "completed", "failed", etc.)
        started: When FOV processing started
        completed: When FOV processing completed
        duration_seconds: How long FOV processing took
    """
    if not master_project_file.exists():
        return
        
    # Read current master project data
    with open(master_project_file, "rb") as f:
        master_data = tomllib.load(f)
    
    # Update FOV status
    fov_key = f"fov_{fov_idx:04d}"
    if fov_key in master_data["fovs"]:
        master_data["fovs"][fov_key]["status"] = status
        
        if started:
            master_data["fovs"][fov_key]["started"] = started.isoformat()
        if completed:
            master_data["fovs"][fov_key]["completed"] = completed.isoformat()
        if duration_seconds is not None:
            master_data["fovs"][fov_key]["duration_seconds"] = duration_seconds
    
    # Update overall progress counters
    completed_count = sum(1 for fov in master_data["fovs"].values() if fov["status"] == "completed")
    failed_count = sum(1 for fov in master_data["fovs"].values() if fov["status"] == "failed")
    
    master_data["processing"]["completed_fovs"] = completed_count
    master_data["processing"]["failed_fovs"] = failed_count
    
    # Write back to file
    write_toml_with_none_removal(master_project_file, master_data)


def finalize_master_project_file(
    master_project_file: Path,
    success: bool,
    statistics: dict = None
):
    """
    Finalize master project file after all FOV processing completion.
    
    Args:
        master_project_file: Path to master project TOML file
        success: Whether all processing completed successfully
        statistics: Optional aggregated processing statistics
    """
    if not master_project_file.exists():
        return
        
    # Read current master project data
    with open(master_project_file, "rb") as f:
        master_data = tomllib.load(f)
    
    now = datetime.now(timezone.utc)
    started_time = datetime.fromisoformat(master_data["processing"]["started"])
    duration = (now - started_time).total_seconds()
    
    # Update processing status
    master_data["processing"]["status"] = "completed" if success else "failed"
    master_data["processing"]["completed"] = now.isoformat()
    master_data["processing"]["duration_seconds"] = duration
    
    # Update statistics if provided
    if statistics:
        master_data["statistics"].update(statistics)
    
    # Write back to file
    write_toml_with_none_removal(master_project_file, master_data)


def load_master_project_file(master_project_file: Path) -> dict:
    """
    Load master project metadata from TOML file.
    
    Args:
        master_project_file: Path to master project TOML file
        
    Returns:
        Master project metadata dictionary
    """
    if not master_project_file.exists():
        raise FileNotFoundError(f"Master project file not found: {master_project_file}")
        
    with open(master_project_file, "rb") as f:
        return tomllib.load(f)


def find_master_project_file(directory: Path) -> Path | None:
    """
    Find a master project file in the given directory.
    
    Args:
        directory: Directory to search in
        
    Returns:
        Path to master project file or None if not found
    """
    master_project_file = directory / "pyama_master_project.toml"
    return master_project_file if master_project_file.exists() else None
"""
Processing results discovery and loading utilities.
"""

from pathlib import Path
from typing_extensions import TypedDict


class ProcessingResults(TypedDict, total=False):
    project_path: Path
    nd2_file: str
    n_fov: int
    fov_data: dict[int, dict[str, Path]]


def discover_processing_results(output_dir: Path) -> ProcessingResults:
    if not output_dir.exists():
        raise FileNotFoundError(f"Output directory not found: {output_dir}")

    all_dirs = list(output_dir.iterdir())
    fov_dirs = [d for d in all_dirs if d.is_dir() and d.name.startswith("fov_")]
    if not fov_dirs:
        raise ValueError(f"No FOV directories found in {output_dir}")

    fov_data: dict[int, dict[str, Path]] = {}
    for fov_dir in sorted(fov_dirs):
        fov_idx = int(fov_dir.name.split("_")[1])
        data_files: dict[str, Path] = {}

        for npy_file in fov_dir.glob("*.npy"):
            stem = npy_file.stem
            if f"_fov{fov_idx:04d}_" in stem:
                parts = stem.split(f"_fov{fov_idx:04d}_")
                if len(parts) > 1:
                    key = parts[1]
                else:
                    key = stem.split("_fov")[0]
                    if "_" in key:
                        key_parts = key.split("_")
                        key = "_".join(key_parts[1:]) if len(key_parts) > 1 else key
            else:
                key = stem.split("_fov")[0]
                if "_" in key:
                    key_parts = key.split("_")
                    key = "_".join(key_parts[1:]) if len(key_parts) > 1 else key
            data_files[key] = npy_file

        traces_files = list(fov_dir.glob("*traces*.csv"))
        if traces_files:
            inspected = [f for f in traces_files if "traces_inspected.csv" in f.name]
            if inspected:
                data_files["traces"] = inspected[0]
            else:
                regular = [
                    f for f in traces_files if "traces.csv" in f.name and "inspected" not in f.name
                ]
                if regular:
                    data_files["traces"] = regular[0]

        fov_data[fov_idx] = data_files

    nd2_file = ""
    if fov_data:
        first_fov_files = list(fov_data.values())[0]
        for file_path in first_fov_files.values():
            parts = file_path.stem.split("_fov")
            if len(parts) > 0:
                nd2_file = parts[0] + ".nd2"
                break

    result = ProcessingResults(
        project_path=output_dir,
        nd2_file=nd2_file,
        n_fov=len(fov_data),
        fov_data=fov_data,
    )
    return result



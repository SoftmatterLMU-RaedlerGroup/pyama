"""
CSV data loading utilities for time-series fluorescence data.

Handles various CSV formats including:
- Simple CSV: First column is time, other columns are cell IDs
- FOV traces: Standard trace format with cell_id, frame, and intensity columns
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any


def load_simple_csv(csv_path: Path) -> pd.DataFrame:
    """
    Load a simple CSV file with time in first column and cell data in other columns.

    Args:
        csv_path: Path to the CSV file

    Returns:
        DataFrame in long format with columns: cell_id, frame, time, intensity_total
    """
    # Read CSV - skip first row (column indices), first column is time
    df = pd.read_csv(csv_path, skiprows=1, header=None, index_col=0)
    
    # Get time values from index
    time_values = df.index.values
    
    # df.columns will be integer indices (1, 2, 3, ...) after reading with header=None
    # Use these directly as cell IDs
    cell_ids = [str(col) for col in df.columns]
    
    # Convert to long format
    records = []
    for i, cell_id in enumerate(cell_ids):
        # Get intensity values for this cell
        cell_values = df.iloc[:, i].values
        
        # Create records for this cell
        for frame_idx, (time, intensity) in enumerate(zip(time_values, cell_values)):
            records.append({
                "cell_id": cell_id,
                "frame": frame_idx,
                "time": time,
                "intensity_total": intensity,
            })
    
    return pd.DataFrame(records)


def discover_simple_csv_files(data_path: Path | str) -> Dict[str, Path]:
    """
    Discover simple CSV files for analysis.

    Args:
        data_path: Path to a CSV file or directory containing CSV files

    Returns:
        Dictionary mapping identifiers to CSV file paths
    """
    data_path = Path(data_path)

    csv_files = {}

    if data_path.is_file() and data_path.suffix.lower() == ".csv":
        # Single CSV file
        csv_name = data_path.stem
        csv_files[csv_name] = data_path

    elif data_path.is_dir():
        # Directory of CSV files
        for csv_path in data_path.glob("*.csv"):
            # Skip files that are already analysis outputs
            if "_fitted" not in csv_path.name and "_traces" not in csv_path.name:
                csv_name = csv_path.stem
                csv_files[csv_name] = csv_path

    return csv_files


def create_simple_csv_batches(
    csv_files: Dict[str, Path], batch_size: int = 10
) -> List[List[Tuple[str, Path]]]:
    """
    Create batches of CSV files for parallel processing.

    Args:
        csv_files: Dictionary mapping names to CSV file paths
        batch_size: Number of cells to process per batch (not files)

    Returns:
        List of batches, each containing (identifier, path) tuples
    """
    # For simple CSV files, we typically have one file with many cells
    # So we'll process each file as its own batch
    batches = []

    for name, path in csv_files.items():
        # Each CSV file becomes its own batch
        batches.append([(name, path)])

    return batches


def discover_trace_files(data_folder: Path) -> Dict[str, Path]:
    """
    Discover trace CSV files in FOV subdirectories.

    Args:
        data_folder: Root folder containing fov_xxxx subdirectories

    Returns:
        Dictionary mapping FOV names to trace file paths
    """
    trace_files = {}

    if not data_folder.exists():
        return trace_files

    # Find FOV directories
    fov_dirs = [
        d for d in data_folder.iterdir() if d.is_dir() and d.name.startswith("fov_")
    ]

    for fov_dir in fov_dirs:
        # Look for trace CSV files
        trace_csvs = list(fov_dir.glob("*_traces.csv"))

        if trace_csvs:
            # Use first trace file found
            trace_files[fov_dir.name] = trace_csvs[0]

    return trace_files


def create_fov_batches(
    fov_trace_files: Dict[str, Path], batch_size: int = 10
) -> List[List[Tuple[str, Path]]]:
    """
    Create batches of FOVs for parallel processing.

    Args:
        fov_trace_files: Dictionary mapping FOV names to trace file paths
        batch_size: Number of FOVs per batch

    Returns:
        List of batches, each containing (fov_name, path) tuples
    """
    fov_items = list(fov_trace_files.items())

    batches = []
    for i in range(0, len(fov_items), batch_size):
        batch = fov_items[i : i + batch_size]
        batches.append(batch)

    return batches


def process_simple_csv_batch(
    csv_paths: List[Tuple[str, Path]],
    model_type: str,
    fitting_params: Dict[str, Any],
    log_queue: Any = None,
) -> Dict[str, Any]:
    """
    Process a batch of simple CSV files for trace fitting.

    This function is designed to work with the existing fitting infrastructure
    but handles simple CSV format instead of FOV-based traces.

    Args:
        csv_paths: List of (name, csv_path) tuples
        model_type: Type of model to fit
        fitting_params: Dictionary of fitting parameters
        log_queue: Optional queue for logging

    Returns:
        Dictionary containing batch results and statistics
    """
    import logging
    from logging.handlers import QueueHandler
    from pyama_qt.analysis.utils.fitting import fit_trace_data

    # Set up logging in worker process
    if log_queue is not None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        if not root_logger.handlers:
            handler = QueueHandler(log_queue)
            root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)

    batch_results = {
        "fov_results": {},  # Keep this key for compatibility
        "total_cells": 0,
        "successful_fits": 0,
        "failed_fits": 0,
        "processing_errors": [],
    }

    try:
        for csv_name, csv_path in csv_paths:
            logger.info(f"Processing CSV: {csv_name}")

            try:
                # Load and convert the simple CSV
                if not csv_path.exists():
                    error_msg = f"CSV file not found: {csv_path}"
                    logger.error(error_msg)
                    batch_results["processing_errors"].append(error_msg)
                    continue

                # Load data in long format
                traces_df = load_simple_csv(csv_path)

                # Get unique cell IDs
                cell_ids = traces_df["cell_id"].unique()
                cell_results = []

                logger.info(f"Fitting {len(cell_ids)} cells in {csv_name}")

                # Fit each cell
                for cell_id in cell_ids:
                    batch_results["total_cells"] += 1

                    try:
                        # Perform fitting using existing infrastructure
                        fit_result = fit_trace_data(
                            traces_df,
                            model_type,
                            cell_id,
                            **fitting_params.get("model_params", {}),
                        )

                        # Build result record
                        result_record = {
                            "dataset": csv_name,
                            "cell_id": cell_id,
                            "model_type": model_type,
                        }
                        result_record.update(fit_result.to_dict())

                        cell_results.append(result_record)

                        if fit_result.success:
                            batch_results["successful_fits"] += 1
                        else:
                            batch_results["failed_fits"] += 1

                    except Exception as e:
                        error_msg = (
                            f"Error fitting cell {cell_id} in {csv_name}: {str(e)}"
                        )
                        logger.error(error_msg)
                        batch_results["processing_errors"].append(error_msg)
                        batch_results["failed_fits"] += 1

                # Save results to CSV
                if cell_results:
                    results_df = pd.DataFrame(cell_results)

                    # Determine output path
                    output_path = csv_path.parent / f"{csv_path.stem}_fitted.csv"
                    results_df.to_csv(output_path, index=False)

                    logger.info(f"Saved {len(cell_results)} results to {output_path}")

                    # Store results in batch (using fov_results for compatibility)
                    batch_results["fov_results"][csv_name] = {
                        "output_path": str(output_path),
                        "n_cells": len(cell_results),
                        "successful_fits": sum(1 for r in cell_results if r["success"]),
                        "results": cell_results,
                    }

            except Exception as e:
                error_msg = f"Error processing CSV {csv_name}: {str(e)}"
                logger.exception(error_msg)
                batch_results["processing_errors"].append(error_msg)

        logger.info(
            f"Batch completed: {batch_results['successful_fits']}/{batch_results['total_cells']} successful fits"
        )

    except Exception as e:
        error_msg = f"Critical error in batch processing: {str(e)}"
        logger.exception(error_msg)
        batch_results["processing_errors"].append(error_msg)

    return batch_results

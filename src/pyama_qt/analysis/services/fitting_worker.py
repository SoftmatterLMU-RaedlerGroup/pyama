"""
Worker functions for processing FOV batches in parallel.

Handles fitting multiple FOVs in separate processes.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional
import logging
from logging.handlers import QueueHandler

from ..utils.fitting import fit_trace_data


def process_fov_batch(
    fov_paths: List[Tuple[str, Path]],
    model_type: str,
    fitting_params: Dict[str, Any],
    log_queue: Optional[Any] = None,
) -> Dict[str, Any]:
    """
    Process a batch of FOVs for trace fitting.

    This function runs in a separate process and fits all cells
    in the given FOVs using the specified model.

    Args:
        fov_paths: List of (fov_name, trace_csv_path) tuples
        model_type: Type of model to fit ('maturation', 'twostage', 'trivial')
        fitting_params: Dictionary of fitting parameters
        log_queue: Optional queue for logging from worker processes

    Returns:
        Dictionary containing batch results and statistics
    """
    # Set up logging in worker process
    if log_queue is not None:
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        if not root_logger.handlers:
            handler = QueueHandler(log_queue)
            root_logger.addHandler(handler)

    logger = logging.getLogger(__name__)

    batch_results = {
        "fov_results": {},
        "total_cells": 0,
        "successful_fits": 0,
        "failed_fits": 0,
        "processing_errors": [],
    }

    try:
        for fov_name, trace_path in fov_paths:
            logger.info(f"Processing FOV: {fov_name}")

            try:
                # Load trace data
                if not trace_path.exists():
                    error_msg = f"Trace file not found: {trace_path}"
                    logger.error(error_msg)
                    batch_results["processing_errors"].append(error_msg)
                    continue

                traces_df = pd.read_csv(trace_path)

                if "cell_id" not in traces_df.columns:
                    error_msg = f"No 'cell_id' column in {trace_path}"
                    logger.error(error_msg)
                    batch_results["processing_errors"].append(error_msg)
                    continue

                # Get unique cell IDs
                cell_ids = traces_df["cell_id"].unique()
                fov_cell_results = []

                logger.info(f"Fitting {len(cell_ids)} cells in {fov_name}")

                # Fit each cell
                for cell_id in cell_ids:
                    batch_results["total_cells"] += 1

                    try:
                        # Perform fitting
                        fit_result = fit_trace_data(
                            traces_df,
                            model_type,
                            cell_id,
                            **fitting_params.get("model_params", {}),
                        )

                        # Build result record
                        result_record = {
                            "fov": fov_name,
                            "cell_id": cell_id,
                            "model_type": model_type,
                        }
                        result_record.update(fit_result.to_dict())

                        fov_cell_results.append(result_record)

                        if fit_result.success:
                            batch_results["successful_fits"] += 1
                        else:
                            batch_results["failed_fits"] += 1

                    except Exception as e:
                        error_msg = (
                            f"Error fitting cell {cell_id} in {fov_name}: {str(e)}"
                        )
                        logger.error(error_msg)
                        batch_results["processing_errors"].append(error_msg)
                        batch_results["failed_fits"] += 1

                # Save FOV results to CSV
                if fov_cell_results:
                    results_df = pd.DataFrame(fov_cell_results)

                    # Determine output path
                    output_path = trace_path.parent / f"{trace_path.stem}_fitted.csv"
                    results_df.to_csv(output_path, index=False)

                    logger.info(
                        f"Saved {len(fov_cell_results)} results to {output_path}"
                    )

                    # Store results in batch
                    batch_results["fov_results"][fov_name] = {
                        "output_path": str(output_path),
                        "n_cells": len(fov_cell_results),
                        "successful_fits": sum(
                            1 for r in fov_cell_results if r["success"]
                        ),
                        "results": fov_cell_results,
                    }

            except Exception as e:
                error_msg = f"Error processing FOV {fov_name}: {str(e)}"
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

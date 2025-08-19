"""
Workflow coordination for sequential trace fitting analysis.

Manages sequential execution of fitting across multiple FOVs.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal, Slot
import logging
from typing import Dict, Any, Optional
import pandas as pd

from ..utils.fitting import fit_trace_data
from pyama_qt.utils.csv_loader import (
    discover_csv_files,
    load_csv_data,
)
from pyama_qt.utils.logging_config import get_logger


class AnalysisWorkflowCoordinator(QObject):
    """Coordinates sequential execution of trace fitting workflow."""

    progress_updated = Signal(int)
    status_updated = Signal(str)
    error_occurred = Signal(str)
    batch_completed = Signal(str, dict)
    workflow_completed = Signal(bool, str)

    def __init__(self, data_folder: Path, model_type: str, fitting_params: Dict[str, Any], batch_size: int, n_workers: int, data_format: str, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._is_cancelled = False
        self.logger = get_logger(__name__)
        self.data_folder = data_folder
        self.model_type = model_type
        self.fitting_params = fitting_params

    @Slot()
    def run(self):
        """Public slot to start the workflow. Connect QThread.started to this."""
        self.run_fitting_workflow()

    def run_fitting_workflow(self) -> bool:
        """
        Run the trace fitting workflow sequentially.
        This method is blocking (within its own thread) but uses signals to update the UI.
        """
        self._is_cancelled = False
        overall_success = False

        try:
            self.status_updated.emit("Discovering CSV files...")
            trace_files = discover_csv_files(self.data_folder)

            if not trace_files:
                self.error_occurred.emit(f"No CSV files found in {self.data_folder}")
                return False

            self.status_updated.emit(f"Found {len(trace_files)} dataset(s) to process")

            total_cells = 0
            successful_fits = 0
            failed_fits = 0
            all_errors = []
            total_files = len(trace_files)
            processed_cells_count = 0

            def progress_callback(cell_id):
                nonlocal processed_cells_count
                processed_cells_count += 1
                if processed_cells_count % 30 == 0:
                    self.logger.info(f"Processed {processed_cells_count} cells...")
                    self.status_updated.emit(f"Processed {processed_cells_count} cells...")

            for i, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    break
                
                self.logger.info(f"Processing file {i+1}/{total_files}: {trace_path.name}")
                self.status_updated.emit(f"Processing {trace_path.name}...")

                try:
                    traces_df = load_csv_data(trace_path)
                    cell_ids = traces_df["cell_id"].unique()
                    file_cell_results = []

                    for cell_id in cell_ids:
                        if self._is_cancelled:
                            break

                        try:
                            fit_result = fit_trace_data(
                                traces_df, self.model_type, cell_id, progress_callback=progress_callback, **self.fitting_params
                            )
                            result_record = {
                                "file": trace_path.stem,
                                "cell_id": cell_id,
                                "model_type": self.model_type,
                            }
                            result_record.update(fit_result.to_dict())
                            file_cell_results.append(result_record)

                            if fit_result.success:
                                successful_fits += 1
                            else:
                                failed_fits += 1

                        except Exception as e:
                            error_msg = f"Error fitting cell {cell_id} in {trace_path.name}: {e}"
                            self.logger.error(error_msg)
                            all_errors.append(error_msg)
                            failed_fits += 1

                    total_cells += len(cell_ids)

                    if file_cell_results:
                        results_df = pd.DataFrame(file_cell_results)
                        output_path = trace_path.parent / f"{trace_path.stem}_fitted.csv"
                        results_df.to_csv(output_path, index=False)
                        self.logger.info(f"Saved {len(file_cell_results)} results to {output_path}")
                        self.batch_completed.emit(trace_path.stem, {"output_path": str(output_path)})

                except Exception as e:
                    error_msg = f"Error processing file {trace_path.name}: {e}"
                    self.logger.exception(error_msg)
                    all_errors.append(error_msg)
                
                progress = int(((i + 1) / total_files) * 100)
                self.progress_updated.emit(progress)

            final_message = f"Fitting completed: {successful_fits}/{total_cells} cells ({(successful_fits/total_cells*100) if total_cells > 0 else 0:.1f}% success rate)"
            self.status_updated.emit(final_message)

            if all_errors:
                for error in all_errors[:5]:
                    self.error_occurred.emit(f"Warning: {error}")

            overall_success = successful_fits > 0
            self.workflow_completed.emit(overall_success, str(self.data_folder))

        except Exception as e:
            error_msg = f"Critical error in fitting workflow: {str(e)}"
            self.logger.exception(error_msg)
            self.error_occurred.emit(error_msg)
            overall_success = False
        
        return overall_success

    def cancel_workflow(self):
        """Cancel the running workflow."""
        self._is_cancelled = True
        self.status_updated.emit("Cancelling workflow...")
        self.logger.info("Workflow cancellation requested")

def get_default_fitting_params() -> Dict[str, Any]:
    return {"model_params": {}}

def validate_fitting_params(params: Dict[str, Any]) -> Dict[str, Any]:
    validated = get_default_fitting_params()
    if "model_params" in params and isinstance(params["model_params"], dict):
        validated["model_params"] = params["model_params"].copy()
    return validated

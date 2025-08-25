"""
Worker for sequential trace fitting analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal
import pandas as pd
import logging

from ..utils.trace_fitting import fit_trace_data
from pyama_core.io.csv_loader import discover_csv_files, load_csv_data


class AnalysisWorker(QObject):
    """Worker class for trace fitting analysis in a background thread."""

    # Signals for communication with the main thread
    progress_updated = Signal(str)  # Message about current progress
    file_processed = Signal(str)  # Emitted when a file is processed (file name)
    finished = Signal()  # Emitted when all processing is complete
    error_occurred = Signal(str)  # Emitted when an error occurs

    def __init__(self, data_folder: Path, model_type: str, fitting_params: dict | None = None):
        """
        Initialize the worker.

        Args:
            data_folder: Path to folder containing CSV files
            model_type: Type of model to fit ('trivial', 'maturation', etc.)
            fitting_params: Optional fitting parameters including initial values
        """
        super().__init__()
        self.data_folder = data_folder
        self.model_type = model_type
        self.fitting_params = fitting_params or {}
        self._is_cancelled = False
        self.logger = logging.getLogger(__name__)

    def process_data(self):
        """Process trace data in the background thread."""
        try:
            # Discover files
            self.progress_updated.emit("Discovering CSV files...")
            trace_files = discover_csv_files(self.data_folder)
            
            if not trace_files:
                self.error_occurred.emit(f"No CSV files found in {self.data_folder}")
                return
            
            self.progress_updated.emit(f"Found {len(trace_files)} file(s)")
            
            # Process each file
            for i, trace_path in enumerate(trace_files):
                if self._is_cancelled:
                    self.progress_updated.emit("Processing cancelled")
                    break
                
                self.progress_updated.emit(
                    f"Processing {trace_path.name} ({i+1}/{len(trace_files)})..."
                )
                
                try:
                    # Load data
                    df = load_csv_data(trace_path)
                    n_cells = df.shape[1]
                    results = []
                    
                    self.logger.info(f"Fitting {n_cells} cells from {trace_path.name}")

                    def progress_callback(cell_id):
                        if cell_id % 30 == 0 or cell_id == n_cells - 1:
                            progress_percent = int((cell_id + 1) / n_cells * 100)
                            progress_msg = (
                                f"Fitting cell {cell_id + 1}/{n_cells} ({progress_percent}%) "
                                f"in {trace_path.name}..."
                            )
                            # Emit signal for UI status bar
                            self.progress_updated.emit(progress_msg)
                            # Log to file/console
                            self.logger.info(progress_msg)
                    
                    # Fit each cell
                    for cell_idx in range(n_cells):
                        if self._is_cancelled:
                            break
                        
                        try:
                            fit_result = fit_trace_data(
                                df, 
                                self.model_type, 
                                cell_idx,
                                progress_callback=progress_callback,
                                user_params=self.fitting_params.get("model_params"),
                                user_bounds=self.fitting_params.get("model_bounds")
                            )
                            
                            # Prepare result record
                            record = {
                                "cell_id": cell_idx,
                                "model_type": self.model_type,
                                "success": fit_result.success,
                                "r_squared": fit_result.r_squared,
                            }
                            record.update(fit_result.fitted_params)
                            results.append(record)
                            
                        except Exception as e:
                            self.logger.error(f"Error fitting cell {cell_idx}: {e}")
                            # Continue with other cells
                            continue
                    
                    # Save results
                    if results:
                        results_df = pd.DataFrame(results)
                        output_path = trace_path.parent / f"{trace_path.stem}_fitted.csv"
                        results_df.to_csv(output_path, index=False)
                        self.logger.info(f"Saved {len(results)} results to {output_path}")
                        
                        # Notify that this file is processed
                        self.file_processed.emit(trace_path.name)
                    
                except Exception as e:
                    self.logger.error(f"Error processing {trace_path.name}: {e}")
                    self.error_occurred.emit(f"Error processing {trace_path.name}: {e}")
                    # Continue with other files
                    continue
            
            self.progress_updated.emit("Completed processing all files")
            
        except Exception as e:
            self.logger.exception(f"Critical error: {e}")
            self.error_occurred.emit(f"Critical error: {e}")
        finally:
            self.finished.emit()

    def cancel(self):
        """Cancel the processing."""
        self._is_cancelled = True
        self.logger.info("Processing cancellation requested")
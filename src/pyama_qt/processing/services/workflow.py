"""
Workflow coordination for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import logging

from .copy import CopyService
from .binarization import BinarizationService
from .background_correction import BackgroundCorrectionService
from .trace_extraction import TraceExtractionService
from ..logging_config import get_logger



def process_fov_range(
    fov_indices: list[int],
    data_info: dict[str, object],
    output_dir: Path,
    params: dict[str, object],
) -> tuple[list[int], int, int, str]:
    """
    Process a range of FOVs through all steps (except copy).
    This function runs in a separate process.
    
    Args:
        fov_indices: List of FOV indices to process
        data_info: Metadata from file loading
        output_dir: Output directory for results
        params: Processing parameters
        
    Returns:
        Tuple of (fov_indices, successful_count, failed_count, message)
    """
    successful_count = 0
    failed_count = 0
    failed_fovs = []
    
    try:
        # Create services without Qt parent (for multiprocessing)
        binarization = BinarizationService(None)
        background_correction = BackgroundCorrectionService(None)
        trace_extraction = TraceExtractionService(None)
        
        # Set up logging in worker process
        logger = logging.getLogger('pyama_qt.processing.services.workflow')
        
        # Use process_all_fovs for each service
        logger.info(f"[Worker] Processing FOVs {fov_indices[0]}-{fov_indices[-1]}")
        
        # Stage 1: Binarization for all FOVs
        logger.info(f"[Worker] Starting Binarization for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        
        success = binarization.process_all_fovs(
            data_info=data_info,
            output_dir=output_dir,
            params={'mask_size': params.get('mask_size', 3)},
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1]
        )
        
        if not success:
            return fov_indices, 0, len(fov_indices), f"Binarization failed for FOVs {fov_indices[0]}-{fov_indices[-1]}"
        
        # Stage 2: Background correction for all FOVs
        logger.info(f"[Worker] Starting Background Correction for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        
        success = background_correction.process_all_fovs(
            data_info=data_info,
            output_dir=output_dir,
            params={
                'div_horiz': params.get('div_horiz', 7),
                'div_vert': params.get('div_vert', 5)
            },
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1]
        )
        
        if not success:
            return fov_indices, 0, len(fov_indices), f"Background correction failed for FOVs {fov_indices[0]}-{fov_indices[-1]}"
        
        # Stage 3: Trace extraction for all FOVs
        logger.info(f"[Worker] Starting Trace Extraction for FOVs {fov_indices[0]}-{fov_indices[-1]}")
        
        success = trace_extraction.process_all_fovs(
            data_info=data_info,
            output_dir=output_dir,
            params={'min_trace_length': params.get('min_trace_length', 3)},
            fov_start=fov_indices[0],
            fov_end=fov_indices[-1]
        )
        
        if not success:
            return fov_indices, 0, len(fov_indices), f"Trace extraction failed for FOVs {fov_indices[0]}-{fov_indices[-1]}"
        
        # All successful
        successful_count = len(fov_indices)
        success_msg = f"Completed processing FOVs {fov_indices[0]}-{fov_indices[-1]}"
        logger.info(f"[Worker] {success_msg}")
        return fov_indices, successful_count, 0, success_msg
        
    except Exception as e:
        error_msg = f"Error processing FOVs {fov_indices[0]}-{fov_indices[-1]}: {str(e)}"
        return fov_indices, 0, len(fov_indices), error_msg


class WorkflowCoordinator(QObject):
    """Coordinates parallel execution of processing workflow."""
    
    progress_updated = Signal(int)  # Overall progress percentage
    status_updated = Signal(str)   # Status message
    error_occurred = Signal(str)   # Error message
    
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.copy_service = CopyService(self)
        self._is_cancelled = False
        self.logger = get_logger(__name__)
        
    def run_complete_workflow(
        self,
        nd2_path: str,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
        fov_start: int | None = None,
        fov_end: int | None = None,
        batch_size: int = 4,
        n_workers: int = 4,
    ) -> bool:
        """
        Run the processing workflow with batch extraction and parallel processing.
        
        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            fov_start: Starting FOV index (inclusive), None for 0
            fov_end: Ending FOV index (inclusive), None for last FOV
            batch_size: Number of FOVs to extract at once
            n_workers: Number of parallel workers for processing
            
        Returns:
            bool: True if all steps completed successfully
        """
        overall_success = False
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            n_fov = data_info["metadata"]["n_fov"]
            
            # Determine FOV range
            if fov_start is None:
                fov_start = 0
            if fov_end is None:
                fov_end = n_fov - 1
                
            # Validate range
            if fov_start < 0 or fov_end >= n_fov or fov_start > fov_end:
                error_msg = f"Invalid FOV range: {fov_start}-{fov_end} (file has {n_fov} FOVs)"
                self.error_occurred.emit(error_msg)
                return False
            
            total_fovs = fov_end - fov_start + 1
            fov_indices = list(range(fov_start, fov_end + 1))
            
            # Process in batches
            completed_fovs = 0
            
            for batch_start in range(0, total_fovs, batch_size):
                if self._is_cancelled:
                    self.status_updated.emit("Processing cancelled")
                    return False
                
                # Get current batch
                batch_end = min(batch_start + batch_size, total_fovs)
                batch_fovs = fov_indices[batch_start:batch_end]
                
                self.logger.info(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
                self.status_updated.emit(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
                
                # Stage 1: Extract batch from ND2 to NPY
                extraction_success = self.copy_service.process_batch(
                    nd2_path, batch_fovs, data_info, output_dir, params
                )
                
                if not extraction_success:
                    self.error_occurred.emit(f"Failed to extract batch starting at FOV {batch_fovs[0]}")
                    return False
                
                # Stage 2: Process extracted FOVs in parallel
                self.logger.info(f"Processing batch in parallel with {n_workers} workers")
                self.status_updated.emit(f"Processing batch in parallel with {n_workers} workers")
                
                # Process FOVs in parallel without progress queue
                
                try:
                    with ProcessPoolExecutor(max_workers=n_workers) as executor:
                        # Distribute FOVs among workers
                        fovs_per_worker = len(batch_fovs) // n_workers
                        remainder = len(batch_fovs) % n_workers
                        
                        # Create FOV ranges for each worker
                        worker_ranges = []
                        start_idx = 0
                        for i in range(n_workers):
                            # Distribute remainder FOVs among first workers
                            count = fovs_per_worker + (1 if i < remainder else 0)
                            if count > 0:
                                end_idx = start_idx + count
                                worker_ranges.append(batch_fovs[start_idx:end_idx])
                                start_idx = end_idx
                        
                        # Submit ranges to workers
                        futures = {
                            executor.submit(
                                process_fov_range,
                                fov_range,
                                data_info,
                                output_dir,
                                params
                            ): fov_range
                            for fov_range in worker_ranges if fov_range
                        }
                    
                    # Track completion
                    for future in as_completed(futures):
                        if self._is_cancelled:
                            executor.shutdown(wait=False)
                            return False
                        
                        fov_range = futures[future]
                        try:
                            fov_indices, successful, failed, message = future.result()
                            self.logger.info(message)
                            self.status_updated.emit(message)
                            
                            completed_fovs += successful
                            
                            if failed > 0:
                                self.error_occurred.emit(f"{failed} FOVs failed in range {fov_indices[0]}-{fov_indices[-1]}")
                                
                        except Exception as e:
                            error_msg = f"Worker exception for FOVs {fov_range[0]}-{fov_range[-1]}: {str(e)}"
                            self.error_occurred.emit(error_msg)
                            # Count all as failed
                            failed_count = len(fov_range)
                        
                        # Update overall progress
                        progress = int(completed_fovs / total_fovs * 100)
                        self.progress_updated.emit(progress)
                    
                finally:
                    pass
                
                # Optional: Clean up raw NPY files after successful processing
                if params.get("delete_raw_after_processing", False):
                    self._cleanup_raw_files(batch_fovs, data_info, output_dir)
            
            overall_success = completed_fovs > 0
            msg = f"Completed processing {completed_fovs}/{total_fovs} FOVs"
            self.logger.info(msg)
            self.status_updated.emit(msg)
            return overall_success
            
        except Exception as e:
            error_msg = f"Error in parallel workflow: {str(e)}"
            self.error_occurred.emit(error_msg)
            return False
            
        finally:
            pass
    
    def _cleanup_raw_files(self, fov_indices: list[int], data_info: dict[str, object], output_dir: Path):
        """Delete raw NPY files after successful processing."""
        base_name = data_info["filename"].replace(".nd2", "")
        
        for fov_idx in fov_indices:
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            
            # Delete raw files
            pc_raw = fov_dir / f"{base_name}_fov{fov_idx:04d}_phase_contrast_raw.npy"
            fl_raw = fov_dir / f"{base_name}_fov{fov_idx:04d}_fluorescence_raw.npy"
            
            if pc_raw.exists():
                pc_raw.unlink()
            if fl_raw.exists():
                fl_raw.unlink()
                
            self.logger.debug(f"Cleaned up raw files for FOV {fov_idx}")
    
    def cancel(self):
        """Cancel the current processing operation."""
        self._is_cancelled = True
        self.copy_service.cancel()
        self.logger.info("Cancelling workflow...")
        self.status_updated.emit("Cancelling workflow...")
    
    def get_all_services(self) -> list:
        """Get all processing services for signal connection."""
        # Only return the copy service since other services run in separate processes
        return [self.copy_service]
"""
Workflow coordination for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject, Signal
from concurrent.futures import ProcessPoolExecutor, as_completed
import multiprocessing as mp
import time

from .copy import CopyService
from .binarization import BinarizationService
from .background_correction import BackgroundCorrectionService
from .trace_extraction import TraceExtractionService



def process_single_fov(
    fov_index: int,
    data_info: dict[str, object],
    output_dir: Path,
    params: dict[str, object],
) -> tuple[int, bool, str]:
    """
    Process a single FOV through all steps (except copy).
    This function runs in a separate process.
    
    Args:
        fov_index: Field of view index to process
        data_info: Metadata from file loading
        output_dir: Output directory for results
        params: Processing parameters
        
    Returns:
        Tuple of (fov_index, success, message)
    """
    try:
        # Create services without Qt parent (for multiprocessing)
        binarization = BinarizationService(None)
        background_correction = BackgroundCorrectionService(None)
        trace_extraction = TraceExtractionService(None)
        
        # Process through each step
        steps = [
            ("Binarization", binarization),
            ("Background Correction", background_correction),
            ("Trace Extraction", trace_extraction),
        ]
        
        fov_output_dir = output_dir / f"fov_{fov_index:04d}"
        
        for step_name, service in steps:
            print(f"FOV {fov_index}: Running {step_name}")
            step_start_time = time.time()
            
            # Process FOV
            success = service.process_fov(
                fov_index, data_info, output_dir, params
            )
            
            step_duration = time.time() - step_start_time
            
            if not success:
                error_msg = f"FOV {fov_index}: Failed at {step_name}"
                return fov_index, False, error_msg
        
        success_msg = f"FOV {fov_index}: Completed all processing steps"
        return fov_index, True, success_msg
        
    except Exception as e:
        error_msg = f"FOV {fov_index}: Error - {str(e)}"
        return fov_index, False, error_msg


class WorkflowCoordinator(QObject):
    """Coordinates parallel execution of processing workflow."""
    
    progress_updated = Signal(int)  # Overall progress percentage
    status_updated = Signal(str)   # Status message
    error_occurred = Signal(str)   # Error message
    
    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self.copy_service = CopyService(self)
        self._is_cancelled = False
        
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
                
                self.status_updated.emit(f"Extracting batch: FOVs {batch_fovs[0]}-{batch_fovs[-1]}")
                
                # Stage 1: Extract batch from ND2 to NPY
                extraction_success = self.copy_service.process_batch(
                    nd2_path, batch_fovs, data_info, output_dir, params
                )
                
                if not extraction_success:
                    self.error_occurred.emit(f"Failed to extract batch starting at FOV {batch_fovs[0]}")
                    return False
                
                # Stage 2: Process extracted FOVs in parallel
                self.status_updated.emit(f"Processing batch in parallel with {n_workers} workers")
                
                with ProcessPoolExecutor(max_workers=n_workers) as executor:
                    # Submit all FOVs in batch for processing
                    futures = {
                        executor.submit(
                            process_single_fov,
                            fov_idx,
                            data_info,
                            output_dir,
                            params
                        ): fov_idx
                        for fov_idx in batch_fovs
                    }
                    
                    # Track completion
                    for future in as_completed(futures):
                        if self._is_cancelled:
                            executor.shutdown(wait=False)
                            return False
                        
                        fov_idx = futures[future]
                        try:
                            fov_index, success, message = future.result()
                            self.status_updated.emit(message)
                            
                            if success:
                                completed_fovs += 1
                            else:
                                self.error_occurred.emit(message)
                                # Don't fail entire workflow for single FOV failure
                                
                        except Exception as e:
                            error_msg = f"FOV {fov_idx}: Exception - {str(e)}"
                            self.error_occurred.emit(error_msg)
                        
                        # Update overall progress
                        progress = int(completed_fovs / total_fovs * 100)
                        self.progress_updated.emit(progress)
                
                # Optional: Clean up raw NPY files after successful processing
                if params.get("delete_raw_after_processing", False):
                    self._cleanup_raw_files(batch_fovs, data_info, output_dir)
            
            overall_success = completed_fovs > 0
            self.status_updated.emit(f"Completed processing {completed_fovs}/{total_fovs} FOVs")
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
                
            self.status_updated.emit(f"Cleaned up raw files for FOV {fov_idx}")
    
    def cancel(self):
        """Cancel the current processing operation."""
        self._is_cancelled = True
        self.copy_service.cancel()
        self.status_updated.emit("Cancelling workflow...")
    
    def get_all_services(self) -> list:
        """Get all processing services for signal connection."""
        # Only return the copy service since other services run in separate processes
        return [self.copy_service]
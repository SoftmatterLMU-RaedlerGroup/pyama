"""
Workflow coordination service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from PySide6.QtCore import QObject
import time
from datetime import datetime, timezone

from .base import BaseProcessingService
from .binarization import BinarizationService
from .background_correction import BackgroundCorrectionService
from .trace_extraction import TraceExtractionService
from ...core.project import (
    create_project_file,
    create_master_project_file,
    update_project_step_status,
    update_project_fov_status,
    update_master_project_fov_status,
    finalize_project_file,
    finalize_master_project_file
)


class WorkflowCoordinator(QObject):
    """Coordinates the execution of all processing steps in sequence."""

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)

        # Initialize processing services
        self.binarization_service = BinarizationService(self)
        self.background_correction_service = BackgroundCorrectionService(self)
        self.trace_extraction_service = TraceExtractionService(self)

        # Define processing order
        self.processing_steps = [
            self.binarization_service,
            self.background_correction_service,
            self.trace_extraction_service,
        ]

    def run_complete_workflow(
        self,
        nd2_path: str,
        data_info: dict[str, object],
        output_dir: Path,
        params: dict[str, object],
    ) -> bool:
        """
        Run the complete processing workflow FOV by FOV with project file management.

        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters

        Returns:
            bool: True if all steps completed successfully
        """
        master_project_file = None
        overall_success = False
        
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)

            # Create master project file for the entire ND2
            master_project_file = create_master_project_file(
                output_dir, nd2_path, data_info, params
            )
            print(f"Created master project file: {master_project_file}")

            n_fov = data_info["metadata"]["n_fov"]
            step_names = [service.get_step_name() for service in self.processing_steps]
            step_timing = {name: [] for name in step_names}  # Track timing per step
            
            # Process each FOV completely through all steps
            for fov_idx in range(n_fov):
                print(f"Processing FOV {fov_idx + 1}/{n_fov}")
                fov_start_time = datetime.now(timezone.utc)

                # Create FOV-specific output directory
                fov_output_dir = output_dir / f"fov_{fov_idx:04d}"
                fov_output_dir.mkdir(parents=True, exist_ok=True)

                # Update master project that this FOV has started
                if master_project_file:
                    update_master_project_fov_status(
                        master_project_file, fov_idx, "started", started=fov_start_time
                    )

                # Create individual FOV project file
                fov_project_file = create_project_file(
                    fov_output_dir, nd2_path, data_info, params
                )
                print(f"  Created FOV project file: {fov_project_file}")

                # Run all processing steps for this FOV
                fov_success = True
                for step_service in self.processing_steps:
                    step_name = step_service.get_step_name()
                    step_start_time = time.time()
                    
                    print(f"  Running {step_name}...")
                    success = step_service.process_fov(
                        nd2_path, fov_idx, data_info, fov_output_dir, params
                    )
                    
                    step_duration = time.time() - step_start_time
                    step_timing[step_name].append(step_duration)
                    
                    # Update FOV project step status
                    if fov_project_file:
                        update_project_step_status(
                            fov_project_file, 
                            step_name.lower().replace(" ", "_"),
                            "completed" if success else "failed",
                            step_duration
                        )
                    
                    if not success:
                        print(f"Failed to process FOV {fov_idx} in step {step_name}")
                        fov_success = False
                        break

                # Calculate FOV completion time
                fov_end_time = datetime.now(timezone.utc)
                fov_duration = (fov_end_time - fov_start_time).total_seconds()

                # Update FOV status in individual project file
                if fov_project_file:
                    update_project_fov_status(
                        fov_project_file, 
                        fov_idx, 
                        "completed" if fov_success else "failed"
                    )
                    finalize_project_file(fov_project_file, fov_success)

                # Update FOV status in master project file
                if master_project_file:
                    update_master_project_fov_status(
                        master_project_file, 
                        fov_idx, 
                        "completed" if fov_success else "failed",
                        started=fov_start_time,
                        completed=fov_end_time,
                        duration_seconds=fov_duration
                    )

                if not fov_success:
                    return False

                print(f"FOV {fov_idx + 1} completed successfully")

            print("All FOVs processed successfully")
            overall_success = True
            return True

        except Exception as e:
            print(f"Error in workflow coordination: {str(e)}")
            return False
            
        finally:
            # Finalize master project file regardless of success/failure
            if master_project_file:
                # TODO: Add statistics collection (cell counts, etc.)
                statistics = {
                    "total_cells_tracked": None,  # Will be calculated later
                    "average_trace_length": None,  # Will be calculated later
                    "processing_errors": 0 if overall_success else 1,
                }
                
                finalize_master_project_file(master_project_file, overall_success, statistics)

    def get_all_services(self) -> list[BaseProcessingService]:
        """Get all processing services for signal connection."""
        return self.processing_steps

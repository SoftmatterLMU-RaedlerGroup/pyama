"""
Workflow coordination service for PyAMA-Qt microscopy image analysis.
"""

from pathlib import Path
from typing import Dict, Any, Optional, List
from PySide6.QtCore import QObject

from .base import BaseProcessingService
from .binarization import BinarizationService
from .background_correction import BackgroundCorrectionService
from .bbox_export import BoundingBoxExportService


class WorkflowCoordinator(QObject):
    """Coordinates the execution of all processing steps in sequence."""
    
    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        
        # Initialize processing services
        self.binarization_service = BinarizationService(self)
        self.background_correction_service = BackgroundCorrectionService(self)
        self.bbox_export_service = BoundingBoxExportService(self)
        
        # Define processing order
        self.processing_steps = [
            self.binarization_service,
            self.background_correction_service,
            # Cell tracking step would go here (not implemented yet)
            self.bbox_export_service
        ]
    
    def run_complete_workflow(self, nd2_path: str, data_info: Dict[str, Any], 
                             output_dir: Path, params: Dict[str, Any]) -> bool:
        """
        Run the complete processing workflow on all FOVs.
        
        Args:
            nd2_path: Path to ND2 file
            data_info: Metadata from file loading
            output_dir: Output directory for results
            params: Processing parameters
            
        Returns:
            bool: True if all steps completed successfully
        """
        try:
            # Ensure output directory exists
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Process each step in sequence
            for step_service in self.processing_steps:
                success = step_service.process_all_fovs(nd2_path, data_info, output_dir, params)
                if not success:
                    return False
            
            return True
            
        except Exception as e:
            print(f"Error in workflow coordination: {str(e)}")
            return False
    
    def get_all_services(self) -> List[BaseProcessingService]:
        """Get all processing services for signal connection."""
        return self.processing_steps
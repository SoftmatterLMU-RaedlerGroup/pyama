"""
Workflow widget for PyAMA-Qt processing application.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox,
    QPushButton, QLineEdit,
    QFileDialog, QSpinBox, QFormLayout
)
from PySide6.QtCore import Signal

from pyama_qt.core.logging_config import get_logger


class Workflow(QWidget):
    """Widget for configuring and controlling the processing workflow."""
    process_requested = Signal(dict)
    
    def __init__(self):
        super().__init__()
        self.data_info = None
        self.logger = get_logger(__name__)
        self.setup_ui()
        
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Output section
        self.setup_output_section(layout)
        
        # Processing section
        self.setup_processing_section(layout)
        
        # Stretch to push everything to top
        layout.addStretch()
        
        
        
        
    def setup_output_section(self, layout):
        """Set up output settings section"""
        output_group = QGroupBox("Output Settings")
        output_layout = QFormLayout(output_group)
        output_layout.setSpacing(8)
        output_layout.setContentsMargins(10, 10, 10, 10)
        
        # Base output directory
        dir_layout = QHBoxLayout()
        self.output_dir = QLineEdit()
        self.output_dir.setPlaceholderText("Select output directory...")
        self.output_dir_button = QPushButton("Browse...")
        self.output_dir_button.clicked.connect(self.select_output_directory)
        
        dir_layout.addWidget(self.output_dir, 1)
        dir_layout.addWidget(self.output_dir_button)
        output_layout.addRow("Output Directory:", dir_layout)
        
        # FOV start
        self.fov_start_spin = QSpinBox()
        self.fov_start_spin.setMinimum(0)
        self.fov_start_spin.setMaximum(99999)
        self.fov_start_spin.setValue(0)
        self.fov_start_spin.setToolTip("Starting field of view (0-based)")
        output_layout.addRow("FOV Start:", self.fov_start_spin)
        
        # FOV end
        self.fov_end_spin = QSpinBox()
        self.fov_end_spin.setMinimum(0)
        self.fov_end_spin.setMaximum(99999)
        self.fov_end_spin.setValue(0)
        self.fov_end_spin.setSpecialValueText("")
        self.fov_end_spin.setToolTip("Ending field of view (0-based)")
        output_layout.addRow("FOV End:", self.fov_end_spin)
        
        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(100)
        self.batch_size_spin.setValue(4)
        self.batch_size_spin.setToolTip("Number of FOVs to extract and process in each batch")
        output_layout.addRow("Batch Size:", self.batch_size_spin)
        
        # Number of workers
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setMinimum(1)
        self.num_workers_spin.setMaximum(32)
        self.num_workers_spin.setValue(4)
        self.num_workers_spin.setToolTip("Number of parallel worker processes")
        output_layout.addRow("Workers:", self.num_workers_spin)
        
        layout.addWidget(output_group)
        
    def setup_processing_section(self, layout):
        """Set up processing controls section"""
        process_group = QGroupBox("Processing Control")
        process_layout = QVBoxLayout(process_group)
        process_layout.setSpacing(8)
        process_layout.setContentsMargins(10, 10, 10, 10)
        
        # Process button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        self.process_button.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 10px;
                border: none;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        process_layout.addWidget(self.process_button)
        
        layout.addWidget(process_group)
        
        
        
            
    def set_data_available(self, available, data_info=None):
        """Called when data becomes available or unavailable"""
        self.data_info = data_info
        
        if available and data_info:
            # Enable processing if we have at least one channel
            pc_channel = data_info.get('pc_channel')
            fl_channel = data_info.get('fl_channel')
            can_process = pc_channel is not None or fl_channel is not None
            self.process_button.setEnabled(can_process)
            
            # Update FOV range based on ND2 data
            n_fov = data_info.get('n_fov', 0)
            if n_fov > 0:
                # Update maximum values
                self.fov_start_spin.setMaximum(n_fov - 1)
                self.fov_end_spin.setMaximum(n_fov - 1)
                
                # Set FOV end to last FOV (n_fov - 1)
                self.fov_end_spin.setValue(n_fov - 1)
            
        else:
            self.process_button.setEnabled(False)
            # Reset FOV spinboxes when no data
            self.fov_start_spin.setValue(0)
            self.fov_end_spin.setValue(0)
            
    def select_output_directory(self):
        """Open directory dialog to select output directory"""
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", "")
        
        if directory:
            self.output_dir.setText(directory)
            self.logger.info(f"Output directory selected: {directory}")
            
            
    def start_processing(self):
        """Start the complete workflow processing"""
        if not self.data_info:
            return
            
        # Validate inputs
        output_dir = self.output_dir.text().strip()
        if not output_dir:
            self.logger.error("No output directory selected")
            return
            
        # Get FOV parameters
        fov_start = self.fov_start_spin.value()
        fov_end = self.fov_end_spin.value()  # Always use the actual value
        batch_size = self.batch_size_spin.value()
        n_workers = self.num_workers_spin.value()
        
        # Validate batch size is divisible by workers
        if batch_size % n_workers != 0:
            self.logger.error(f"Batch size ({batch_size}) must be divisible by number of workers ({n_workers})")
            self.logger.error("Please adjust batch size or workers so that batch_size % workers = 0")
            return
        
        # Validate FOV range
        if fov_end < fov_start:
            self.logger.error("FOV End must be greater than or equal to FOV Start")
            return
            
        # Use ND2 filename as base name
        base_name = self.data_info['filename'].split('.')[0]
            
        # All steps are enabled by default
        enabled_steps = ['segmentation', 'background_correction', 'tracking', 'bounding_box']
            
        # Prepare processing parameters with default values
        params = {
            'data_info': self.data_info,
            'output_dir': output_dir,
            'base_name': base_name,
            'enabled_steps': enabled_steps,
            
            # FOV and batch parameters
            'fov_start': fov_start,
            'fov_end': fov_end,
            'batch_size': batch_size,
            'n_workers': n_workers,
            
            # Default parameters for all steps
            'mask_size': 3,
            'div_horiz': 7,
            'div_vert': 5,
            'use_memmap': True,
            'max_displacement': 20,
            'memory_frames': 3,
        }
        
        # Emit signal to start processing
        self.process_requested.emit(params)
        
        # Update UI for processing state
        self.process_button.setEnabled(False)
        self.fov_start_spin.setEnabled(False)
        self.fov_end_spin.setEnabled(False)
        self.batch_size_spin.setEnabled(False)
        self.num_workers_spin.setEnabled(False)
        
        # Log workflow info
        fov_range = f"{fov_start}-{fov_end}"
        self.logger.info(f"Starting complete workflow (FOV {fov_range})...")
        self.logger.info(f"Batch size: {batch_size}, Workers: {n_workers}")
        self.logger.info("Processing stages: Binarization → Background Correction → Trace Extraction")
        self.logger.info(f"Parameters: mask_size={params['mask_size']}, div_horiz={params['div_horiz']}, div_vert={params['div_vert']}")
        
        
    def update_progress(self, value, message=""):
        """Update status"""
        if message:
            self.logger.info(message)
            
            
    def processing_finished(self, success, message=""):
        """Called when processing is complete"""
        self.process_button.setEnabled(True)
        self.fov_start_spin.setEnabled(True)
        self.fov_end_spin.setEnabled(True)
        self.batch_size_spin.setEnabled(True)
        self.num_workers_spin.setEnabled(True)
        
        if success:
            self.logger.info("✓ Complete workflow finished successfully")
            if message:
                self.logger.info(message)
        else:
            self.logger.error(f"✗ Workflow failed: {message}")
            
    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.processing_finished(False, error_message)
        
        
        
        

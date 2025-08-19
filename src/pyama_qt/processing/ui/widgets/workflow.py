"""
Workflow widget for PyAMA-Qt processing application.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGroupBox,
    QPushButton,
    QComboBox,
    QLabel,
    QLineEdit,
    QFileDialog,
    QSpinBox,
    QFormLayout,
    QGridLayout,
)
from PySide6.QtCore import Signal

from pyama_qt.utils.logging_config import get_logger


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
        """Set up output section"""
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        output_layout.setSpacing(8)
        output_layout.setContentsMargins(10, 10, 10, 10)

        # Base output directory
        dir_header_layout = QHBoxLayout()
        dir_label = QLabel("Save Directory:")
        self.dir_button = QPushButton("Browse...")
        self.dir_button.clicked.connect(self.select_output_directory)

        dir_header_layout.addWidget(dir_label)
        dir_header_layout.addStretch()
        dir_header_layout.addWidget(self.dir_button)

        self.save_dir = QLineEdit("")
        self.save_dir.setReadOnly(True)

        output_layout.addRow(dir_header_layout)
        output_layout.addRow(self.save_dir)

        layout.addWidget(output_group)

    def setup_processing_section(self, layout):
        """Set up processing controls section"""
        process_group = QGroupBox("Processing Settings")
        process_layout = QVBoxLayout(process_group)
        process_layout.setSpacing(8)
        process_layout.setContentsMargins(10, 10, 10, 10)

        # Create grid layout for FOV and processing settings
        grid_layout = QGridLayout()
        grid_layout.setSpacing(8)

        # FOV start
        self.fov_start_spin = QSpinBox()
        self.fov_start_spin.setMinimum(0)
        self.fov_start_spin.setMaximum(99999)
        self.fov_start_spin.setValue(0)
        self.fov_start_spin.setToolTip("Starting field of view (0-based)")
        grid_layout.addWidget(QLabel("FOV Start:"), 0, 0)
        grid_layout.addWidget(self.fov_start_spin, 0, 1)

        # FOV end
        self.fov_end_spin = QSpinBox()
        self.fov_end_spin.setMinimum(0)
        self.fov_end_spin.setMaximum(99999)
        self.fov_end_spin.setValue(0)
        self.fov_end_spin.setSpecialValueText("")
        self.fov_end_spin.setToolTip("Ending field of view (0-based)")
        grid_layout.addWidget(QLabel("FOV End:"), 0, 2)
        grid_layout.addWidget(self.fov_end_spin, 0, 3)

        # Batch size
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setMinimum(1)
        self.batch_size_spin.setMaximum(100)
        self.batch_size_spin.setValue(2)
        self.batch_size_spin.setToolTip(
            "Number of FOVs to extract and process in each batch"
        )
        grid_layout.addWidget(QLabel("Batch Size:"), 1, 0)
        grid_layout.addWidget(self.batch_size_spin, 1, 1)

        # Number of workers
        self.num_workers_spin = QSpinBox()
        self.num_workers_spin.setMinimum(1)
        self.num_workers_spin.setMaximum(32)
        self.num_workers_spin.setValue(2)
        self.num_workers_spin.setToolTip("Number of parallel worker processes")
        grid_layout.addWidget(QLabel("Workers:"), 1, 2)
        grid_layout.addWidget(self.num_workers_spin, 1, 3)

        process_layout.addLayout(grid_layout)

        # Background correction method
        self.bg_correction_combo = QComboBox()
        self.bg_correction_combo.addItems(["None", "Schwarzfischer"])
        self.bg_correction_combo.setCurrentText("None")  # Default
        self.bg_correction_combo.setToolTip(
            "Background correction method (None skips background correction)"
        )

        # Create horizontal layout with stretch
        bg_correction_layout = QHBoxLayout()
        bg_correction_label = QLabel("Background Correction:")
        bg_correction_layout.addWidget(bg_correction_label)
        bg_correction_layout.addStretch()
        bg_correction_layout.addWidget(self.bg_correction_combo)

        process_layout.addLayout(bg_correction_layout)

        # Process button
        self.process_button = QPushButton("Start Complete Workflow")
        self.process_button.setEnabled(False)
        self.process_button.clicked.connect(self.start_processing)
        process_layout.addWidget(self.process_button)

        layout.addWidget(process_group)

    def set_data_available(self, available, data_info=None):
        """Called when data becomes available or unavailable"""
        self.data_info = data_info

        if available and data_info:
            # Enable processing if we have at least one channel
            pc_channel = data_info.get("pc_channel")
            fl_channel = data_info.get("fl_channel")
            can_process = pc_channel is not None or fl_channel is not None
            self.process_button.setEnabled(can_process)

            # Update FOV range based on ND2 data
            n_fov = data_info.get("n_fov", 0)
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
            self, "Select Output Directory", ""
        )

        if directory:
            self.save_dir.setText(directory)
            self.logger.info(f"Output directory selected: {directory}")

    def start_processing(self):
        """Start the complete workflow processing"""
        if not self.data_info:
            return

        # Validate inputs
        output_dir = self.save_dir.text().strip()
        if not output_dir:
            self.logger.error("No output directory selected")
            return

        # Get FOV parameters
        fov_start = self.fov_start_spin.value()
        fov_end = self.fov_end_spin.value()  # Always use the actual value
        batch_size = self.batch_size_spin.value()
        n_workers = self.num_workers_spin.value()
        bg_correction_method = self.bg_correction_combo.currentText()

        # Validate batch size is divisible by workers
        if batch_size % n_workers != 0:
            self.logger.error(
                f"Batch size ({batch_size}) must be divisible by number of workers ({n_workers})"
            )
            self.logger.error(
                "Please adjust batch size or workers so that batch_size % workers = 0"
            )
            return

        # Validate FOV range
        if fov_end < fov_start:
            self.logger.error("FOV End must be greater than or equal to FOV Start")
            return

        # Use ND2 filename as base name
        base_name = self.data_info["filename"].split(".")[0]

        # All steps are enabled by default
        enabled_steps = [
            "segmentation",
            "background_correction",
            "tracking",
            "bounding_box",
        ]

        # Prepare processing parameters with default values
        params = {
            "data_info": self.data_info,
            "output_dir": output_dir,
            "base_name": base_name,
            "enabled_steps": enabled_steps,
            # FOV and batch parameters
            "fov_start": fov_start,
            "fov_end": fov_end,
            "batch_size": batch_size,
            "n_workers": n_workers,
            # Background correction setting
            "background_correction_method": bg_correction_method,
            # Default parameters for all steps
            "mask_size": 3,
            "div_horiz": 7,
            "div_vert": 5,
            "min_trace_length": 20,
        }

        # Emit signal to start processing
        self.process_requested.emit(params)

        # Update UI for processing state
        self.process_button.setEnabled(False)
        self.fov_start_spin.setEnabled(False)
        self.fov_end_spin.setEnabled(False)
        self.batch_size_spin.setEnabled(False)
        self.num_workers_spin.setEnabled(False)
        self.bg_correction_combo.setEnabled(False)

        # Log workflow info
        fov_range = f"{fov_start}-{fov_end}"
        self.logger.info(f"Starting complete workflow (FOV {fov_range})...")
        self.logger.info(f"Batch size: {batch_size}, Workers: {n_workers}")
        if bg_correction_method == "None":
            self.logger.info(
                "Processing stages: Binarization → Trace Extraction (no background correction)"
            )
        else:
            self.logger.info(
                f"Processing stages: Binarization → Background Correction ({bg_correction_method}) → Trace Extraction"
            )
        self.logger.info(
            f"Parameters: mask_size={params['mask_size']}, div_horiz={params['div_horiz']}, div_vert={params['div_vert']}"
        )

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
        self.bg_correction_combo.setEnabled(True)

        if success:
            self.logger.info("✓ Complete workflow finished successfully")
            if message:
                self.logger.info(message)
        else:
            self.logger.error(f"✗ Workflow failed: {message}")

    def processing_error(self, error_message):
        """Called when processing encounters an error"""
        self.processing_finished(False, error_message)

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
from dataclasses import dataclass
from pathlib import Path

from pyama_qt.utils.logging_config import get_logger


@dataclass(slots=True)
class ProcessingParams:
	"""View-model for processing parameter collection and validation."""
	output_dir: str
	data_info: dict
	fov_start: int
	fov_end: int
	batch_size: int
	n_workers: int
	binarization_method: str
	background_correction_method: str
	mask_size: int
	div_horiz: int
	div_vert: int
	footprint_size: int

	def as_dict(self) -> dict:
		return {
			"data_info": self.data_info,
			"output_dir": self.output_dir,
			"base_name": self.data_info["filename"].split(".")[0],
			"enabled_steps": [
				"segmentation",
				"background_correction",
				"tracking",
				"bounding_box",
			],
			"fov_start": self.fov_start,
			"fov_end": self.fov_end,
			"batch_size": self.batch_size,
			"n_workers": self.n_workers,
			"binarization_method": self.binarization_method,
			"background_correction_method": self.background_correction_method,
			"mask_size": self.mask_size,
			"div_horiz": self.div_horiz,
			"div_vert": self.div_vert,
			"footprint_size": self.footprint_size,
			"min_trace_length": 20,
		}

	def validate(self) -> None:
		if not self.output_dir:
			raise ValueError("Output directory is required")
		if self.fov_end < self.fov_start:
			raise ValueError("FOV End must be >= FOV Start")
		if self.batch_size <= 0 or self.n_workers <= 0:
			raise ValueError("Batch size and workers must be positive")
		if self.batch_size % self.n_workers != 0:
			raise ValueError("Batch size must be divisible by number of workers")
		if self.mask_size % 2 == 0:
			raise ValueError("Mask size must be odd")
		if self.footprint_size % 2 == 0:
			raise ValueError("Morph footprint must be odd")


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

        # Binarization method
        self.bin_method_combo = QComboBox()
        self.bin_method_combo.addItems(["log-std", "global-otsu", "cellpose"])
        self.bin_method_combo.setCurrentText("log-std")
        self.bin_method_combo.setToolTip("Segmentation method for phase contrast frames")

        bin_layout = QHBoxLayout()
        bin_label = QLabel("Binarization:")
        bin_layout.addWidget(bin_label)
        bin_layout.addStretch()
        bin_layout.addWidget(self.bin_method_combo)
        process_layout.addLayout(bin_layout)

        # Background correction method
        self.bg_correction_combo = QComboBox()
        self.bg_correction_combo.addItems(["None", "schwarzfischer", "morph-open"])
        self.bg_correction_combo.setCurrentText("None")
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

        # Algorithm parameters
        params_grid = QGridLayout()
        params_grid.setSpacing(8)
        self.mask_size_spin = QSpinBox()
        self.mask_size_spin.setRange(1, 25)
        self.mask_size_spin.setSingleStep(2)
        self.mask_size_spin.setValue(3)
        params_grid.addWidget(QLabel("Mask Size:"), 0, 0)
        params_grid.addWidget(self.mask_size_spin, 0, 1)

        self.div_horiz_spin = QSpinBox()
        self.div_horiz_spin.setRange(1, 25)
        self.div_horiz_spin.setValue(7)
        params_grid.addWidget(QLabel("BG Div Horiz:"), 0, 2)
        params_grid.addWidget(self.div_horiz_spin, 0, 3)

        self.div_vert_spin = QSpinBox()
        self.div_vert_spin.setRange(1, 25)
        self.div_vert_spin.setValue(5)
        params_grid.addWidget(QLabel("BG Div Vert:"), 1, 2)
        params_grid.addWidget(self.div_vert_spin, 1, 3)

        self.footprint_spin = QSpinBox()
        self.footprint_spin.setRange(3, 101)
        self.footprint_spin.setSingleStep(2)
        self.footprint_spin.setValue(25)
        params_grid.addWidget(QLabel("Morph Footprint:"), 1, 0)
        params_grid.addWidget(self.footprint_spin, 1, 1)

        process_layout.addLayout(params_grid)

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

        # Build params via view-model
        vm = ProcessingParams(
            output_dir=self.save_dir.text().strip(),
            data_info=self.data_info,
            fov_start=self.fov_start_spin.value(),
            fov_end=self.fov_end_spin.value(),
            batch_size=self.batch_size_spin.value(),
            n_workers=self.num_workers_spin.value(),
            binarization_method=self.bin_method_combo.currentText(),
            background_correction_method=self.bg_correction_combo.currentText(),
            mask_size=int(self.mask_size_spin.value()),
            div_horiz=int(self.div_horiz_spin.value()),
            div_vert=int(self.div_vert_spin.value()),
            footprint_size=int(self.footprint_spin.value()),
        )

        # Validate and handle errors
        try:
            vm.validate()
        except Exception as e:
            self.logger.error(str(e))
            return

        # Prepare processing parameters dict
        params = vm.as_dict()

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
        fov_range = f"{vm.fov_start}-{vm.fov_end}"
        self.logger.info(f"Starting complete workflow (FOV {fov_range})...")
        self.logger.info(f"Batch size: {vm.batch_size}, Workers: {vm.n_workers}")
        if vm.background_correction_method == "None":
            self.logger.info(
                "Processing stages: Binarization → Trace Extraction (no background correction)"
            )
        else:
            self.logger.info(
                f"Processing stages: Binarization ({vm.binarization_method}) → Background Correction ({vm.background_correction_method}) → Trace Extraction"
            )
        self.logger.info(
            f"Parameters: mask_size={vm.mask_size}, div_horiz={vm.div_horiz}, div_vert={vm.div_vert}, footprint_size={vm.footprint_size}"
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

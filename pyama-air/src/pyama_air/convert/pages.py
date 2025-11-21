"""Convert wizard pages for pyama-air GUI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

logger = logging.getLogger(__name__)


# =============================================================================
# FILE SELECTION PAGE
# =============================================================================


class FileSelectionPage(QWizardPage):
    """Page for selecting input file and output directory."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the file selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("File Selection")
        self.setSubTitle("Select the microscopy file to convert and output directory.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for file selection."""
        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)

        # Input file selection
        input_row = QHBoxLayout()
        input_row.addWidget(QLabel("Input File:"))
        input_row.addStretch()
        self.input_browse_btn = QPushButton("Browse")
        self.input_browse_btn.clicked.connect(self._browse_input)
        input_row.addWidget(self.input_browse_btn)
        file_layout.addLayout(input_row)

        self.input_path_edit = QLineEdit()
        self.input_path_edit.setPlaceholderText("Select microscopy file (ND2, CZI, etc.)...")
        self.input_path_edit.setReadOnly(True)
        file_layout.addWidget(self.input_path_edit)

        # Output directory selection
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output Directory:"))
        output_row.addStretch()
        self.output_browse_btn = QPushButton("Browse")
        self.output_browse_btn.clicked.connect(self._browse_output)
        output_row.addWidget(self.output_browse_btn)
        file_layout.addLayout(output_row)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Select output directory...")
        self.output_dir_edit.setReadOnly(True)
        file_layout.addWidget(self.output_dir_edit)

        layout.addWidget(file_group)

        # File information group
        info_group = QGroupBox("File Information")
        info_layout = QVBoxLayout(info_group)

        self.file_info = QLabel("No file selected")
        self.file_info.setWordWrap(True)
        self.file_info.setStyleSheet("QLabel { color: gray; }")
        info_layout.addWidget(self.file_info)

        layout.addWidget(info_group)

    @Slot()
    def _browse_input(self) -> None:
        """Browse for input microscopy file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Microscopy File",
            "",
            "Microscopy Files (*.nd2 *.czi *.ome.tiff);;ND2 Files (*.nd2);;CZI Files (*.czi);;OME-TIFF Files (*.ome.tiff);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._page_data.input_path = Path(file_path)
            self.input_path_edit.setText(str(self._page_data.input_path))
            self._load_file_info()

            # Set default output directory to input file's parent
            if not self._page_data.output_dir:
                self._page_data.output_dir = self._page_data.input_path.parent
                self.output_dir_edit.setText(str(self._page_data.output_dir))

    @Slot()
    def _browse_output(self) -> None:
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if dir_path:
            self._page_data.output_dir = Path(dir_path)
            self.output_dir_edit.setText(str(self._page_data.output_dir))

    def _load_file_info(self) -> None:
        """Load information about the input file."""
        if not self._page_data.input_path or not self._page_data.input_path.exists():
            return

        try:
            from bioio import BioImage

            image = BioImage(self._page_data.input_path)
            scenes = list(image.scenes)
            n_scenes = len(scenes)
            n_channels = image.dims.C if hasattr(image.dims, "C") else "Unknown"

            info_text = f"File: {self._page_data.input_path.name}\n"
            info_text += f"Scenes: {n_scenes}\n"
            info_text += f"Channels: {n_channels}"

            self.file_info.setText(info_text)
            self.file_info.setStyleSheet("")

            if hasattr(image, "close"):
                try:
                    image.close()
                except Exception:
                    pass

        except Exception as exc:
            logger.error("Failed to read microscopy file: %s", exc)
            self.file_info.setText(f"Error reading file: {exc}")
            self.file_info.setStyleSheet("QLabel { color: red; }")

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        if not self._page_data.input_path or not self._page_data.input_path.exists():
            return False
        if not self._page_data.output_dir:
            return False
        return True


# =============================================================================
# CONFIGURATION PAGE
# =============================================================================


class ConfigurationPage(QWizardPage):
    """Page for configuring conversion mode."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Conversion Mode")
        self.setSubTitle("Select the output mode for conversion.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for configuration."""
        layout = QVBoxLayout(self)

        # Mode selection group
        mode_group = QGroupBox("Output Mode")
        mode_layout = QVBoxLayout(mode_group)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["multi", "split"])
        self.mode_combo.setCurrentText("multi")
        self.mode_combo.currentTextChanged.connect(self._on_mode_changed)

        mode_layout.addWidget(QLabel("Mode:"))
        mode_layout.addWidget(self.mode_combo)

        # Mode description
        self.mode_description = QLabel()
        self.mode_description.setWordWrap(True)
        self._update_mode_description()
        mode_layout.addWidget(self.mode_description)

        layout.addWidget(mode_group)

    @Slot(str)
    def _on_mode_changed(self, mode: str) -> None:
        """Handle mode change."""
        self._page_data.mode = mode
        self._update_mode_description()

    def _update_mode_description(self) -> None:
        """Update the mode description label."""
        mode = self.mode_combo.currentText()
        if mode == "multi":
            self.mode_description.setText(
                "Creates one OME-TIFF file containing all scenes."
            )
        else:
            self.mode_description.setText(
                "Creates one OME-TIFF file per scene (e.g., file_scene0.ome.tiff, file_scene1.ome.tiff)."
            )

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        self._page_data.mode = self.mode_combo.currentText()
        return True


# =============================================================================
# EXECUTION PAGE
# =============================================================================


class ConvertWorker(QObject):
    """Worker for running conversion in background thread."""

    finished = Signal(bool, str, list)  # success, message, output_files

    def __init__(self, input_path: Path, output_dir: Path, mode: str) -> None:
        """Initialize the convert worker."""
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.mode = mode

    def run(self) -> None:
        """Run the conversion operation."""
        try:
            from bioio import BioImage
            from bioio_ome_tiff.writers import OmeTiffWriter

            resolved_input = self.input_path.expanduser().resolve()
            target_dir = self.output_dir.expanduser().resolve()
            resolved_output = target_dir / f"{resolved_input.stem}.ome.tiff"

            mode_normalized = self.mode.lower()
            if mode_normalized not in {"multi", "split"}:
                self.finished.emit(False, f"Invalid mode: {self.mode}", [])
                return

            # Load image
            image = BioImage(resolved_input)

            # Collect scenes
            scene_data = []
            dim_orders = []
            image_names = []
            channel_names = []

            scenes = list(image.scenes)
            for idx, scene in enumerate(scenes):
                image.set_scene(scene)
                scene_data.append(image.data)
                dim_orders.append(image.dims.order)
                image_names.append(
                    str(scene) if isinstance(scene, str) else f"Scene-{idx}"
                )

                # Try to extract channel names
                names = None
                try:
                    da = image.xarray_dask_data
                    ch_coord = da.coords.get("C") if hasattr(da, "coords") else None
                    if ch_coord is not None:
                        try:
                            names = [str(v) for v in ch_coord.values.tolist()]
                        except Exception:
                            names = [str(v) for v in list(ch_coord.values)]
                except Exception:
                    names = None
                channel_names.append(names)

            if not scene_data:
                self.finished.emit(False, "No scenes found in the input file.", [])
                if hasattr(image, "close"):
                    try:
                        image.close()
                    except Exception:
                        pass
                return

            target_dir.mkdir(parents=True, exist_ok=True)
            saved_files: list[Path] = []

            if mode_normalized == "multi":
                logger.info("Saving OME-TIFF with %s scene(s) to %s", len(scene_data), resolved_output)
                OmeTiffWriter.save(
                    scene_data,
                    resolved_output,
                    dim_order=dim_orders,
                    image_name=image_names,
                    channel_names=channel_names,
                )
                saved_files.append(resolved_output)
                message = f"Saved {len(scene_data)} scene(s) to {resolved_output}"
            else:
                for idx, (data, dim_order, name, ch_names) in enumerate(
                    zip(scene_data, dim_orders, image_names, channel_names, strict=False)
                ):
                    scene_output = target_dir / f"{resolved_input.stem}_scene{idx}.ome.tiff"
                    logger.info("Saving scene %s to %s", name, scene_output)
                    OmeTiffWriter.save(
                        data,
                        scene_output,
                        dim_order=dim_order,
                        image_name=name,
                        channel_names=ch_names,
                    )
                    saved_files.append(scene_output)

                message = f"Saved {len(saved_files)} file(s) to {target_dir}"

            if hasattr(image, "close"):
                try:
                    image.close()
                except Exception:
                    pass

            self.finished.emit(True, message, saved_files)

        except Exception as exc:
            logger.error("Conversion failed: %s", exc)
            self.finished.emit(False, f"Conversion failed: {exc}", [])


class ExecutionPage(QWizardPage):
    """Page for executing the conversion."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the execution page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Execute Conversion")
        self.setSubTitle("Review configuration and execute the conversion.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for execution."""
        layout = QVBoxLayout(self)

        # Configuration summary group
        summary_group = QGroupBox("Configuration Summary")
        summary_layout = QVBoxLayout(summary_group)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        summary_layout.addWidget(self.summary_label)

        layout.addWidget(summary_group)

        # Action group
        action_group = QGroupBox("Execution")
        action_layout = QVBoxLayout(action_group)

        # Execute button
        self.execute_btn = QPushButton("Execute Conversion")
        self.execute_btn.clicked.connect(self._execute_conversion)
        action_layout.addWidget(self.execute_btn)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        action_layout.addWidget(self.progress_bar)

        # Status
        self.status_label = QLabel("Ready to execute")
        action_layout.addWidget(self.status_label)

        layout.addWidget(action_group)

        # Worker thread
        self._worker_thread: QThread | None = None
        self._worker: ConvertWorker | None = None

    def initializePage(self) -> None:
        """Initialize the page with configuration summary."""
        config = self.wizard.get_convert_config()
        if not config:
            self.summary_label.setText("Error: Invalid configuration")
            return

        # Build summary text
        summary = "Configuration Summary:\n\n"
        summary += f"Input File: {config.input_path.name}\n"
        summary += f"Output Directory: {config.output_dir}\n"
        summary += f"Mode: {config.mode}\n"
        if config.mode == "multi":
            summary += "\nWill create one OME-TIFF file with all scenes."
        else:
            summary += "\nWill create one OME-TIFF file per scene."

        self.summary_label.setText(summary)

    @Slot()
    def _execute_conversion(self) -> None:
        """Execute the conversion."""
        config = self.wizard.get_convert_config()
        if not config:
            self.status_label.setText("Error: Invalid configuration")
            return

        try:
            self.status_label.setText("Starting conversion...")
            self.execute_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress

            # Create and start worker
            self._worker_thread = QThread()
            self._worker = ConvertWorker(
                input_path=config.input_path,
                output_dir=config.output_dir,
                mode=config.mode,
            )
            self._worker.moveToThread(self._worker_thread)
            self._worker_thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._on_conversion_finished)
            self._worker.finished.connect(self._worker_thread.quit)
            self._worker_thread.finished.connect(self._worker_thread.deleteLater)

            self._worker_thread.start()

        except Exception as exc:
            error_msg = f"Conversion failed: {exc}"
            self.status_label.setText(error_msg)
            self.wizard.convert_finished.emit(False, error_msg)
            logger.error("Conversion execution failed: %s", exc)

    @Slot(bool, str, list)
    def _on_conversion_finished(self, success: bool, message: str, output_files: list) -> None:
        """Handle conversion completion."""
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)

        self._page_data.convert_success = success
        self._page_data.convert_message = message
        self._page_data.output_files = output_files

        if success:
            self.status_label.setText(f"Conversion completed: {message}")
        else:
            self.status_label.setText(f"Conversion failed: {message}")

        # Emit signal for wizard
        self.wizard.convert_finished.emit(success, message)


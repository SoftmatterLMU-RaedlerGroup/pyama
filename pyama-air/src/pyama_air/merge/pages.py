"""Merge wizard pages for pyama-air GUI."""

from __future__ import annotations

import logging
import yaml
from pathlib import Path

from PySide6.QtCore import Slot
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

logger = logging.getLogger(__name__)


# =============================================================================
# SAMPLE CONFIGURATION PAGE
# =============================================================================


class SampleConfigurationPage(QWizardPage):
    """Page for configuring samples."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the sample configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Sample Configuration")
        self.setSubTitle("Define your samples with names and FOV ranges.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for sample configuration."""
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Add samples by providing a name and FOV range (e.g., '0-5, 7, 9-11'). "
            "Click 'Add Sample' to add each sample, then 'Next' when finished."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # Sample input form
        form_layout = QFormLayout()

        self.sample_name_edit = QLineEdit()
        self.sample_name_edit.setPlaceholderText("Enter sample name...")
        form_layout.addRow("Sample Name:", self.sample_name_edit)

        self.fov_range_edit = QLineEdit()
        self.fov_range_edit.setPlaceholderText("e.g., 0-5, 7, 9-11")
        form_layout.addRow("FOV Range:", self.fov_range_edit)

        btn_layout = QHBoxLayout()
        self.add_sample_btn = QPushButton("Add Sample")
        self.add_sample_btn.clicked.connect(self._add_sample)
        btn_layout.addWidget(self.add_sample_btn)

        self.save_samples_btn = QPushButton("Save Samples YAML")
        self.save_samples_btn.clicked.connect(self._save_samples_yaml)
        btn_layout.addWidget(self.save_samples_btn)

        form_layout.addRow("", btn_layout)

        layout.addLayout(form_layout)

        # Sample list
        list_label = QLabel("Configured Samples:")
        layout.addWidget(list_label)

        self.sample_list_widget = QWidget()
        self.sample_list_layout = QVBoxLayout(self.sample_list_widget)
        layout.addWidget(self.sample_list_widget)

    @Slot()
    def _add_sample(self) -> None:
        """Add a new sample."""
        name = self.sample_name_edit.text().strip()
        fov_range = self.fov_range_edit.text().strip()

        if not name:
            self._show_error("Sample name is required")
            return

        if not fov_range:
            self._show_error("FOV range is required")
            return

        # Check for duplicate names
        if any(sample["name"] == name for sample in self._page_data.samples):
            self._show_error(f"Sample '{name}' already exists")
            return

        # Validate FOV range
        try:
            from pyama_core.processing.merge import parse_fov_range

            parse_fov_range(fov_range)
        except ValueError as exc:
            self._show_error(f"Invalid FOV range: {exc}")
            return

        # Add sample
        sample = {"name": name, "fovs": fov_range}
        self._page_data.samples.append(sample)

        # Update UI
        self._update_sample_list()
        self.sample_name_edit.clear()
        self.fov_range_edit.clear()

    def _update_sample_list(self) -> None:
        """Update the sample list display."""
        # Clear existing widgets
        self._clear_layout(self.sample_list_layout)

        if not self._page_data.samples:
            label = QLabel("No samples configured")
            label.setStyleSheet("QLabel { color: gray; }")
            self.sample_list_layout.addWidget(label)
            return

        for i, sample in enumerate(self._page_data.samples):
            sample_widget = QWidget()
            sample_layout = QHBoxLayout(sample_widget)

            # Sample info
            info_label = QLabel(f"{sample['name']}: {sample['fovs']}")
            sample_layout.addWidget(info_label)

            # Remove button
            remove_btn = QPushButton("Remove")
            remove_btn.setProperty("index", i)
            remove_btn.clicked.connect(self._remove_sample)
            sample_layout.addWidget(remove_btn)

            self.sample_list_layout.addWidget(sample_widget)

    def _clear_layout(self, layout: QVBoxLayout) -> None:
        """Clear all widgets from a layout."""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    @Slot()
    def _remove_sample(self) -> None:
        """Remove a sample."""
        sender = self.sender()
        index = sender.property("index")
        if 0 <= index < len(self._page_data.samples):
            self._page_data.samples.pop(index)
            self._update_sample_list()

    @Slot()
    def _save_samples_yaml(self) -> None:
        """Save configured samples to a YAML file."""
        if not self._page_data.samples:
            self._show_error("No samples configured. Add samples before saving.")
            return

        # Prompt for save location
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Samples YAML",
            "samples.yaml",
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if not file_path:
            return

        try:
            yaml_path = Path(file_path)
            yaml_path.parent.mkdir(parents=True, exist_ok=True)

            # Save samples to YAML
            with yaml_path.open("w", encoding="utf-8") as handle:
                yaml.safe_dump(
                    {"samples": self._page_data.samples}, handle, sort_keys=False
                )

            # Update page data with saved path
            self._page_data.sample_yaml_path = yaml_path

            logger.info(
                "Saved %d sample(s) to %s", len(self._page_data.samples), yaml_path
            )
            self._show_success(
                f"Saved {len(self._page_data.samples)} sample(s) to {yaml_path}"
            )

        except Exception as exc:
            error_msg = f"Failed to save samples YAML: {exc}"
            logger.error(error_msg)
            self._show_error(error_msg)

    def _show_error(self, message: str) -> None:
        """Show an error message."""
        # Simple error display - could be enhanced with a proper dialog
        logger.error("Sample configuration error: %s", message)

    def _show_success(self, message: str) -> None:
        """Show a success message."""
        logger.info("Sample configuration success: %s", message)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        return len(self._page_data.samples) > 0


# =============================================================================
# FILE SELECTION PAGE
# =============================================================================


class FileSelectionPage(QWizardPage):
    """Page for selecting files and output directory."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the file selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("File Selection")
        self.setSubTitle(
            "Select the samples YAML file, processing results, and output directory."
        )
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for file selection."""
        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)

        # Sample YAML file
        sample_yaml_row = QHBoxLayout()
        sample_yaml_row.addWidget(QLabel("Samples YAML:"))
        sample_yaml_row.addStretch()
        self.sample_yaml_browse_btn = QPushButton("Browse")
        self.sample_yaml_browse_btn.clicked.connect(self._browse_sample_yaml)
        sample_yaml_row.addWidget(self.sample_yaml_browse_btn)
        file_layout.addLayout(sample_yaml_row)

        self.sample_yaml_edit = QLineEdit()
        self.sample_yaml_edit.setPlaceholderText("Select samples.yaml file...")
        self.sample_yaml_edit.setReadOnly(True)
        file_layout.addWidget(self.sample_yaml_edit)

        # Processing results file
        processing_results_row = QHBoxLayout()
        processing_results_row.addWidget(QLabel("Processing Results:"))
        processing_results_row.addStretch()
        self.processing_results_browse_btn = QPushButton("Browse")
        self.processing_results_browse_btn.clicked.connect(
            self._browse_processing_results
        )
        processing_results_row.addWidget(self.processing_results_browse_btn)
        file_layout.addLayout(processing_results_row)

        self.processing_results_edit = QLineEdit()
        self.processing_results_edit.setPlaceholderText(
            "Select processing_results.yaml file..."
        )
        self.processing_results_edit.setReadOnly(True)
        file_layout.addWidget(self.processing_results_edit)

        # Output directory
        output_row = QHBoxLayout()
        output_row.addWidget(QLabel("Output Directory:"))
        output_row.addStretch()
        self.output_dir_browse_btn = QPushButton("Browse")
        self.output_dir_browse_btn.clicked.connect(self._browse_output_dir)
        output_row.addWidget(self.output_dir_browse_btn)
        file_layout.addLayout(output_row)

        self.output_dir_edit = QLineEdit()
        self.output_dir_edit.setPlaceholderText("Select output directory...")
        self.output_dir_edit.setReadOnly(True)
        file_layout.addWidget(self.output_dir_edit)

        layout.addWidget(file_group)

    @Slot()
    def _browse_sample_yaml(self) -> None:
        """Browse for samples YAML file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Samples YAML File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._page_data.sample_yaml_path = Path(file_path)
            self.sample_yaml_edit.setText(str(self._page_data.sample_yaml_path))

    @Slot()
    def _browse_processing_results(self) -> None:
        """Browse for processing results file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Processing Results File",
            "",
            "YAML Files (*.yaml *.yml);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._page_data.processing_results_path = Path(file_path)
            self.processing_results_edit.setText(
                str(self._page_data.processing_results_path)
            )

    @Slot()
    def _browse_output_dir(self) -> None:
        """Browse for output directory."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if dir_path:
            self._page_data.output_dir = Path(dir_path)
            self.output_dir_edit.setText(str(self._page_data.output_dir))

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        return (
            self._page_data.sample_yaml_path is not None
            and self._page_data.processing_results_path is not None
            and self._page_data.output_dir is not None
        )


# =============================================================================
# EXECUTION PAGE
# =============================================================================


class ExecutionPage(QWizardPage):
    """Page for executing the merge."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the execution page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Execute Merge")
        self.setSubTitle("Review configuration and execute the merge.")
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
        self.execute_btn = QPushButton("Execute Merge")
        self.execute_btn.clicked.connect(self._execute_merge)
        action_layout.addWidget(self.execute_btn)

        # Progress/status
        self.status_label = QLabel("Ready to execute")
        action_layout.addWidget(self.status_label)

        layout.addWidget(action_group)

    def initializePage(self) -> None:
        """Initialize the page with configuration summary."""
        config = self.wizard.get_merge_config()
        if not config:
            self.summary_label.setText("Error: Invalid configuration")
            return

        # Build summary text
        summary = "Configuration Summary:\n\n"
        summary += f"Samples: {len(config.samples)}\n"
        for sample in config.samples:
            summary += f"  {sample['name']}: {sample['fovs']}\n"
        summary += f"\nSamples YAML: {config.sample_yaml_path}\n"
        summary += f"Processing Results: {config.processing_results_path}\n"
        summary += f"Output Directory: {config.output_dir}\n"

        self.summary_label.setText(summary)

    @Slot()
    def _execute_merge(self) -> None:
        """Execute the merge."""
        config = self.wizard.get_merge_config()
        if not config:
            self.status_label.setText("Error: Invalid configuration")
            return

        try:
            self.status_label.setText("Starting merge...")
            self.execute_btn.setEnabled(False)

            # Execute the merge
            from pyama_core.processing.merge import run_merge as run_core_merge

            message = run_core_merge(
                sample_yaml=config.sample_yaml_path,
                processing_results=config.processing_results_path,
                output_dir=config.output_dir,
            )

            self.status_label.setText(f"Merge completed: {message}")
            self.wizard.merge_finished.emit(True, message)

        except Exception as exc:
            error_msg = f"Merge failed: {exc}"
            self.status_label.setText(error_msg)
            self.wizard.merge_finished.emit(False, error_msg)
            logger.error("Merge execution failed: %s", exc)

"""Analysis wizard pages for pyama-air GUI."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QWizard,
    QWizardPage,
)

from pyama_air.utils.threading import BackgroundWorker

logger = logging.getLogger(__name__)


# =============================================================================
# FILE SELECTION PAGE
# =============================================================================


class FileSelectionPage(QWizardPage):
    """Page for selecting CSV file for analysis."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the file selection page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("File Selection")
        self.setSubTitle("Select the CSV file containing trace data to fit.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for file selection."""
        layout = QVBoxLayout(self)

        # File selection group
        file_group = QGroupBox("File Selection")
        file_layout = QVBoxLayout(file_group)

        # CSV file selection
        csv_row = QHBoxLayout()
        csv_row.addWidget(QLabel("CSV File:"))
        csv_row.addStretch()
        self.csv_browse_btn = QPushButton("Browse")
        self.csv_browse_btn.clicked.connect(self._browse_csv)
        csv_row.addWidget(self.csv_browse_btn)
        file_layout.addLayout(csv_row)

        self.csv_path_edit = QLineEdit()
        self.csv_path_edit.setPlaceholderText("Select CSV file...")
        self.csv_path_edit.setReadOnly(True)
        file_layout.addWidget(self.csv_path_edit)

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
    def _browse_csv(self) -> None:
        """Browse for CSV file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CSV File",
            "",
            "CSV Files (*.csv);;All Files (*)",
            options=QFileDialog.Option.DontUseNativeDialog,
        )
        if file_path:
            self._page_data.csv_path = Path(file_path)
            self.csv_path_edit.setText(str(self._page_data.csv_path))
            self._load_file_info()

    def _load_file_info(self) -> None:
        """Load information about the CSV file."""
        if not self._page_data.csv_path or not self._page_data.csv_path.exists():
            return

        try:
            import pandas as pd

            # Try to read a few rows to get info
            df = pd.read_csv(self._page_data.csv_path, nrows=5)
            info_text = f"File: {self._page_data.csv_path.name}\n"
            info_text += f"Columns: {', '.join(df.columns.tolist())}\n"
            info_text += f"Preview: {len(df)} rows shown"

            self.file_info.setText(info_text)
            self.file_info.setStyleSheet("")

        except Exception as exc:
            logger.error("Failed to read CSV file: %s", exc)
            self.file_info.setText(f"Error reading file: {exc}")
            self.file_info.setStyleSheet("QLabel { color: red; }")

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        if not self._page_data.csv_path or not self._page_data.csv_path.exists():
            return False
        return True


# =============================================================================
# CONFIGURATION PAGE
# =============================================================================


class ConfigurationPage(QWizardPage):
    """Page for configuring model and parameters."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the configuration page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Model Configuration")
        self.setSubTitle("Select the model type and configure parameters.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for configuration."""
        layout = QVBoxLayout(self)

        # Model selection group
        model_group = QGroupBox("Model Selection")
        model_layout = QVBoxLayout(model_group)

        model_form = QFormLayout()
        self.model_combo = QComboBox()
        self.model_combo.addItems(self.wizard.get_available_models())
        self.model_combo.currentTextChanged.connect(self._on_model_changed)
        model_form.addRow("Model Type:", self.model_combo)
        model_layout.addLayout(model_form)

        layout.addWidget(model_group)

        # Parameters configuration group
        params_group = QGroupBox("Parameters")
        params_layout = QVBoxLayout(params_group)

        # Manual parameters checkbox
        self.manual_params_checkbox = QCheckBox("Set parameters manually")
        self.manual_params_checkbox.setChecked(False)
        self.manual_params_checkbox.toggled.connect(self._on_manual_mode_toggled)
        params_layout.addWidget(self.manual_params_checkbox)

        # Parameter table (initially hidden)
        self.param_table = QTableWidget()
        self.param_table.setColumnCount(3)
        self.param_table.setHorizontalHeaderLabels(["Parameter", "Value", "Bounds"])
        self.param_table.setVisible(False)
        params_layout.addWidget(self.param_table)

        layout.addWidget(params_group)

        # Set initial model
        if self.wizard.get_available_models():
            self._page_data.model_type = self.wizard.get_available_models()[0]
            self._update_parameter_defaults()

    @Slot(str)
    def _on_model_changed(self, model_type: str) -> None:
        """Handle model type change."""
        self._page_data.model_type = model_type
        self._update_parameter_defaults()

    @Slot(bool)
    def _on_manual_mode_toggled(self, checked: bool) -> None:
        """Handle manual mode toggle."""
        self.param_table.setVisible(checked)

    def _update_parameter_defaults(self) -> None:
        """Update parameter defaults based on selected model."""
        try:
            from pyama_core.analysis.models import get_model

            model = get_model(self._page_data.model_type)

            # Clear existing parameters
            self._page_data.model_params.clear()
            self._page_data.model_bounds.clear()

            # Build parameter dict
            params_dict = {}

            # Add fixed parameters
            for param_name, fixed_param in model.DEFAULT_FIXED.items():
                params_dict[param_name] = {
                    "name": fixed_param.name,
                    "value": fixed_param.value,
                    "min": None,
                    "max": None,
                }
                self._page_data.model_params[param_name] = fixed_param.value

            # Add fit parameters
            for param_name, fit_param in model.DEFAULT_FIT.items():
                params_dict[param_name] = {
                    "name": fit_param.name,
                    "value": fit_param.value,
                    "min": fit_param.lb,
                    "max": fit_param.ub,
                }
                self._page_data.model_params[param_name] = fit_param.value
                self._page_data.model_bounds[param_name] = (fit_param.lb, fit_param.ub)

            # Update table - store param_name as user data in the row
            self.param_table.setRowCount(len(params_dict))
            param_keys = list(params_dict.keys())
            for row, (param_name, param_info) in enumerate(params_dict.items()):
                # Store param_name as user data on the row
                self.param_table.setItem(row, 0, QTableWidgetItem(param_info["name"]))
                # Store param_name as data role for easy retrieval
                name_item = self.param_table.item(row, 0)
                if name_item:
                    name_item.setData(Qt.ItemDataRole.UserRole, param_name)
                
                self.param_table.setItem(
                    row, 1, QTableWidgetItem(str(param_info["value"]))
                )
                if param_info["min"] is not None and param_info["max"] is not None:
                    bounds_str = f"[{param_info['min']}, {param_info['max']}]"
                else:
                    bounds_str = "Fixed"
                self.param_table.setItem(row, 2, QTableWidgetItem(bounds_str))

        except Exception as exc:
            logger.error("Failed to update parameter defaults: %s", exc)

    def validatePage(self) -> bool:
        """Validate the page before proceeding."""
        # Always ensure parameters are set from defaults (in case model changed)
        if self._page_data.model_type:
            self._update_parameter_defaults()
        
        # Collect manual parameter values if manual mode is enabled
        if self.manual_params_checkbox.isChecked():
            for row in range(self.param_table.rowCount()):
                param_name_item = self.param_table.item(row, 0)
                value_item = self.param_table.item(row, 1)
                if param_name_item and value_item:
                    # Get parameter key from user data, fallback to text if not available
                    param_key = param_name_item.data(Qt.ItemDataRole.UserRole)
                    if not param_key:
                        # Fallback: try to find by display name (for backward compatibility)
                        display_name = param_name_item.text()
                        # Try to find matching param key by display name
                        from pyama_core.analysis.models import get_model
                        try:
                            model = get_model(self._page_data.model_type)
                            param_key = None
                            # Search in fixed params
                            for key, param in model.DEFAULT_FIXED.items():
                                if param.name == display_name:
                                    param_key = key
                                    break
                            # Search in fit params if not found
                            if param_key is None:
                                for key, param in model.DEFAULT_FIT.items():
                                    if param.name == display_name:
                                        param_key = key
                                        break
                        except Exception:
                            pass
                    
                    if param_key:
                        try:
                            value = float(value_item.text())
                            self._page_data.model_params[param_key] = value
                        except ValueError:
                            logger.warning("Invalid parameter value: %s", value_item.text())

        return bool(self._page_data.model_type)


# =============================================================================
# EXECUTION PAGE
# =============================================================================


class FittingWorker(QObject):
    """Worker for running fitting in background thread."""

    finished = Signal(bool, str, object)  # success, message, output_path (Path | None)

    def __init__(self, csv_path: Path, model_type: str, model_params: dict, model_bounds: dict) -> None:
        """Initialize the fitting worker."""
        super().__init__()
        self.csv_path = csv_path
        self.model_type = model_type
        self.model_params = model_params
        self.model_bounds = model_bounds

    def run(self) -> None:
        """Run the fitting operation."""
        try:
            from pyama_core.analysis.fitting_service import FittingService

            service = FittingService()
            results_df, saved_path = service.fit_csv_file(
                csv_file=self.csv_path,
                model_type=self.model_type,
                model_params=self.model_params if self.model_params else None,
                model_bounds=self.model_bounds if self.model_bounds else None,
            )

            if saved_path:
                self.finished.emit(True, f"Fitting completed. Results saved to {saved_path}", saved_path)
            else:
                self.finished.emit(False, "Fitting completed but failed to save results", None)

        except Exception as exc:
            logger.error("Fitting failed: %s", exc)
            self.finished.emit(False, f"Fitting failed: {exc}", None)


class ExecutionPage(QWizardPage):
    """Page for executing the fitting."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the execution page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Execute Fitting")
        self.setSubTitle("Review configuration and execute the fitting.")
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
        self.execute_btn = QPushButton("Execute Fitting")
        self.execute_btn.clicked.connect(self._execute_fitting)
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
        self._worker: FittingWorker | None = None

    def initializePage(self) -> None:
        """Initialize the page with configuration summary."""
        config = self.wizard.get_analysis_config()
        if not config:
            self.summary_label.setText("Error: Invalid configuration")
            return

        # Build summary text
        summary = "Configuration Summary:\n\n"
        summary += f"CSV File: {config.csv_path.name}\n"
        summary += f"Model Type: {config.model_type}\n"
        if config.model_params:
            summary += f"Parameters: {len(config.model_params)} configured\n"
        if config.model_bounds:
            summary += f"Bounds: {len(config.model_bounds)} configured\n"

        self.summary_label.setText(summary)

    @Slot()
    def _execute_fitting(self) -> None:
        """Execute the fitting."""
        config = self.wizard.get_analysis_config()
        if not config:
            self.status_label.setText("Error: Invalid configuration")
            return

        try:
            self.status_label.setText("Starting fitting...")
            self.execute_btn.setEnabled(False)
            self.progress_bar.setVisible(True)
            self.progress_bar.setRange(0, 0)  # Indeterminate progress

            # Create and start worker
            self._worker_thread = QThread()
            self._worker = FittingWorker(
                csv_path=config.csv_path,
                model_type=config.model_type,
                model_params=config.model_params,
                model_bounds=config.model_bounds,
            )
            self._worker.moveToThread(self._worker_thread)
            self._worker_thread.started.connect(self._worker.run)
            self._worker.finished.connect(self._on_fitting_finished)
            self._worker.finished.connect(self._worker_thread.quit)
            self._worker_thread.finished.connect(self._worker_thread.deleteLater)

            self._worker_thread.start()

        except Exception as exc:
            error_msg = f"Fitting failed: {exc}"
            self.status_label.setText(error_msg)
            self.wizard.analysis_finished.emit(False, error_msg)
            logger.error("Fitting execution failed: %s", exc)

    @Slot(bool, str, object)
    def _on_fitting_finished(self, success: bool, message: str, output_path: Path | None) -> None:
        """Handle fitting completion."""
        self.progress_bar.setVisible(False)
        self.execute_btn.setEnabled(True)

        self._page_data.fitting_success = success
        self._page_data.fitting_message = message
        self._page_data.fitted_results_path = output_path

        if success:
            self.status_label.setText(f"Fitting completed: {message}")
        else:
            self.status_label.setText(f"Fitting failed: {message}")

        # Emit signal for wizard
        self.wizard.analysis_finished.emit(success, message)


# =============================================================================
# RESULTS PAGE
# =============================================================================


class ResultsPage(QWizardPage):
    """Page for displaying fitting results summary."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the results page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Fitting Results")
        self.setSubTitle("Summary of fitting results.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for results."""
        layout = QVBoxLayout(self)

        # Results summary
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        layout.addWidget(self.summary_label)

        # Results table
        self.results_table = QTableWidget()
        self.results_table.setColumnCount(5)
        self.results_table.setHorizontalHeaderLabels(
            ["FOV", "Cell", "Success", "R²", "Parameters"]
        )
        layout.addWidget(self.results_table)

    def initializePage(self) -> None:
        """Initialize the page with results."""
        if not self._page_data.fitted_results_path or not self._page_data.fitted_results_path.exists():
            self.summary_label.setText("No results available.")
            return

        try:
            import pandas as pd

            df = pd.read_csv(self._page_data.fitted_results_path)

            # Summary statistics
            total_cells = len(df)
            successful = df["success"].sum() if "success" in df.columns else 0
            avg_r2 = df["r_squared"].mean() if "r_squared" in df.columns else 0.0

            summary = f"Fitting Results Summary:\n\n"
            summary += f"Total Cells: {total_cells}\n"
            summary += f"Successful Fits: {successful} ({100*successful/total_cells:.1f}%)\n"
            summary += f"Average R²: {avg_r2:.3f}\n"
            summary += f"\nResults saved to: {self._page_data.fitted_results_path.name}"

            self.summary_label.setText(summary)

            # Populate table with first 100 rows
            display_df = df.head(100)
            self.results_table.setRowCount(len(display_df))

            for row_idx, (_, row) in enumerate(display_df.iterrows()):
                self.results_table.setItem(row_idx, 0, QTableWidgetItem(str(row.get("fov", ""))))
                self.results_table.setItem(row_idx, 1, QTableWidgetItem(str(row.get("cell", ""))))
                self.results_table.setItem(
                    row_idx, 2, QTableWidgetItem(str(row.get("success", False)))
                )
                self.results_table.setItem(
                    row_idx, 3, QTableWidgetItem(f"{row.get('r_squared', 0):.3f}")
                )

                # Parameters column - show first few parameter values
                param_cols = [c for c in df.columns if c not in ["fov", "cell", "model_type", "success", "r_squared"]]
                param_values = [f"{c}={row.get(c, 0):.3f}" for c in param_cols[:3]]
                self.results_table.setItem(
                    row_idx, 4, QTableWidgetItem(", ".join(param_values))
                )

            if len(df) > 100:
                info_label = QLabel(f"Showing first 100 of {len(df)} results")
                self.layout().addWidget(info_label)

        except Exception as exc:
            logger.error("Failed to load results: %s", exc)
            self.summary_label.setText(f"Error loading results: {exc}")


# =============================================================================
# SAVE PAGE
# =============================================================================


class SavePage(QWizardPage):
    """Page for confirming save location."""

    def __init__(self, parent: QWizard) -> None:
        """Initialize the save page."""
        super().__init__(parent)
        self.wizard = parent
        self._page_data = parent.get_page_data()

        self.setTitle("Save Results")
        self.setSubTitle("Fitting results have been saved.")
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the UI for save confirmation."""
        layout = QVBoxLayout(self)

        self.save_label = QLabel()
        self.save_label.setWordWrap(True)
        layout.addWidget(self.save_label)

    def initializePage(self) -> None:
        """Initialize the page with save information."""
        if self._page_data.fitted_results_path:
            text = f"Fitting results have been saved to:\n\n{self._page_data.fitted_results_path}\n\n"
            text += "You can now use this file for further analysis."
            self.save_label.setText(text)
        else:
            self.save_label.setText("No results were saved.")

"""
Data panel widget for loading and visualizing CSV data.
"""

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QPushButton,
    QFileDialog,
    QMessageBox,
    QGroupBox,
)
from PySide6.QtCore import Signal, Slot
from pathlib import Path
import numpy as np
import pandas as pd

from pyama_core.io.csv_loader import load_csv_data
from pyama_qt.utils.logging_config import get_logger
from pyama_qt.widgets.mpl_canvas import MplCanvas


class DataPanel(QWidget):
    """Left panel widget with CSV loading and data visualization."""

    # Signals
    data_loaded = Signal(Path, object)  # csv_path, data (pd.DataFrame)
    fitted_results_found = Signal(object)  # fitted_results_df (pd.DataFrame)

    def __init__(self, parent=None, main_window=None):
        super().__init__(parent)
        self.logger = get_logger(__name__)
        self.main_window = main_window  # Reference to MainWindow for centralized data

        self.setup_ui()

    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)

        # Top-level group: Data
        data_group = QGroupBox("Data")
        data_layout = QVBoxLayout()

        # Load CSV button
        self.load_csv_btn = QPushButton("Load CSV")
        self.load_csv_btn.clicked.connect(self.load_csv_clicked)
        data_layout.addWidget(self.load_csv_btn)

        # All sequences plot
        self.data_canvas = MplCanvas(self, width=5, height=8)
        data_layout.addWidget(self.data_canvas)
        self.data_canvas.clear()

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

    @Slot()
    def load_csv_clicked(self):
        """Handle Load CSV button click."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select CSV File", "", "CSV Files (*.csv)"
        )

        if file_path:
            self.load_csv_file(Path(file_path))

    def load_csv_file(self, csv_path: Path):
        """Load and visualize CSV data."""
        try:
            # Load data in wide format (time as index, cells as columns)
            data = load_csv_data(csv_path)
            n_cells = len(data.columns)
            self.logger.info(f"Loaded {n_cells} cells from {csv_path.name}")

            # Emit signal (MainWindow will store the data centrally)
            self.data_loaded.emit(csv_path, data)

            # Check for corresponding fitted results file
            self.check_for_fitted_results(csv_path)

        except Exception as e:
            self.logger.error(f"Error loading CSV: {e}")
            QMessageBox.critical(self, "Load Error", f"Failed to load CSV:\n{str(e)}")

    def plot_all_sequences(self):
        """Plot all sequences in gray with mean in red."""
        if self.main_window is None or self.main_window.raw_data is None:
            return

        data = self.main_window.raw_data
        time_values = data.index.values

        lines_data = []
        styles_data = []

        for col in data.columns:
            lines_data.append((time_values, data[col].values))
            styles_data.append({"plot_style": "line", "color": "gray", "alpha": 0.2, "linewidth": 0.5})

        if not data.empty:
            lines_data.append((time_values, data.mean(axis=1).values))
            styles_data.append(
                {"plot_style": "line", "color": "red", "linewidth": 2, "label": "Mean"}
            )

        self.data_canvas.plot_lines(
            lines_data,
            styles_data,
            title=f"All Sequences ({len(data.columns)} cells)",
            x_label="Time",
            y_label="Intensity",
        )

    def highlight_cell(self, cell_id: int):
        """Highlight a specific cell in the visualization."""
        if self.main_window is None or self.main_window.raw_data is None:
            return False

        data = self.main_window.raw_data
        time_values = data.index.values

        if cell_id not in data.columns:
            return False

        lines_data = []
        styles_data = []

        for other_id in data.columns[:50]:
            if other_id != cell_id:
                lines_data.append((time_values, data[other_id].values))
                styles_data.append(
                    {"plot_style": "line", "color": "gray", "alpha": 0.1, "linewidth": 0.5}
                )

        lines_data.append((time_values, data[cell_id].values))
        styles_data.append(
            {"plot_style": "line", "color": "blue", "linewidth": 2, "label": f"Cell {cell_id}"}
        )

        self.data_canvas.plot_lines(
            lines_data,
            styles_data,
            title=f"Cell {cell_id} Highlighted",
            x_label="Time",
            y_label="Intensity",
        )
        return True

    def get_random_cell_id(self) -> int | None:
        """Get a random cell ID from the loaded data."""
        if self.main_window is None or self.main_window.raw_data is None:
            return None

        cell_ids = self.main_window.raw_data.columns
        return int(np.random.choice(cell_ids))

    def check_for_fitted_results(self, csv_path: Path):
        """Check if there's a corresponding fitted results file and load it."""
        # Generate potential fitted file path
        fitted_path = csv_path.parent / f"{csv_path.stem}_fitted.csv"
        
        if fitted_path.exists():
            try:
                self.logger.info(f"Found fitted results: {fitted_path.name}")
                fitted_df = pd.read_csv(fitted_path)
                
                if len(fitted_df) > 0:
                    self.fitted_results_found.emit(fitted_df)
                    # Count successful fits for logging
                    if 'success' in fitted_df.columns:
                        n_successful = fitted_df[fitted_df['success'] == True].shape[0]
                        self.logger.info(f"Loaded {len(fitted_df)} fitted results ({n_successful} successful)")
                else:
                    self.logger.warning("Fitted results file is empty")
                    
            except Exception as e:
                self.logger.error(f"Error loading fitted results: {e}")
        else:
            self.logger.debug(f"No fitted results found at: {fitted_path}")
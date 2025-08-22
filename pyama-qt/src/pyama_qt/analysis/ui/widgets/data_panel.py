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

from pyama_qt.utils.csv_loader import load_csv_data
from pyama_qt.utils.logging_config import get_logger
from pyama_qt.utils.mpl_canvas import MplCanvas


class DataPanel(QWidget):
    """Left panel widget with CSV loading and data visualization."""

    # Signals
    data_loaded = Signal(Path, pd.DataFrame)  # csv_path, data
    fitted_results_found = Signal(pd.DataFrame)  # fitted_results_df

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

        # Initialize empty plot
        self.data_ax = self.data_canvas.fig.add_subplot(111)
        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title("All Sequences")
        self.data_ax.grid(True, alpha=0.3)
        self.data_canvas.draw()

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
            # Load data in long format
            data = load_csv_data(csv_path)

            # Get unique cells
            cell_ids = data["cell_id"].unique()
            n_cells = len(cell_ids)

            self.logger.info(f"Loaded {n_cells} cells from {csv_path.name}")

            # Update data plot
            self.plot_all_sequences()

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

        # Clear previous plot
        self.data_ax.clear()

        # Get unique cells
        cell_ids = self.main_window.raw_data["cell_id"].unique()

        # Collect all traces for mean calculation
        all_traces = []

        # Plot each cell in gray
        for cell_id in cell_ids[:100]:  # Limit to first 100 for performance
            cell_data = self.main_window.raw_data[self.main_window.raw_data["cell_id"] == cell_id]
            time = cell_data["time"].values
            intensity = cell_data["intensity_total"].values

            self.data_ax.plot(time, intensity, color="gray", alpha=0.2, linewidth=0.5)
            all_traces.append(intensity)

        # Calculate and plot mean in red
        if all_traces:
            # Ensure all traces have same length
            min_len = min(len(trace) for trace in all_traces)
            all_traces_array = np.array([trace[:min_len] for trace in all_traces])
            mean_trace = np.mean(all_traces_array, axis=0)

            # Get time values for mean
            sample_cell = self.main_window.raw_data[self.main_window.raw_data["cell_id"] == cell_ids[0]]
            time_values = sample_cell["time"].values[:min_len]

            self.data_ax.plot(
                time_values,
                mean_trace,
                color="red",
                linewidth=2,
                label="Mean",
                alpha=0.8,
            )

        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title(f"All Sequences ({len(cell_ids)} cells)")
        self.data_ax.grid(True, alpha=0.3)
        self.data_ax.legend()

        self.data_canvas.draw()

    def highlight_cell(self, cell_id: int):
        """Highlight a specific cell in the visualization."""
        if self.main_window is None or self.main_window.raw_data is None:
            return False

        # Check if cell exists
        if cell_id not in self.main_window.raw_data["cell_id"].values:
            return False

        # Get cell data
        cell_data = self.main_window.raw_data[self.main_window.raw_data["cell_id"] == cell_id]

        # Update data plot to highlight this cell
        self.data_ax.clear()

        # Plot all in gray (faded)
        for other_id in self.main_window.raw_data["cell_id"].unique()[:50]:
            if other_id != cell_id:
                other_data = self.main_window.raw_data[self.main_window.raw_data["cell_id"] == other_id]
                self.data_ax.plot(
                    other_data["time"].values,
                    other_data["intensity_total"].values,
                    color="gray",
                    alpha=0.1,
                    linewidth=0.5,
                )

        # Plot selected cell in blue
        self.data_ax.plot(
            cell_data["time"].values,
            cell_data["intensity_total"].values,
            color="blue",
            linewidth=2,
            label=f"Cell {cell_id}",
        )

        self.data_ax.set_xlabel("Time")
        self.data_ax.set_ylabel("Intensity")
        self.data_ax.set_title(f"Cell {cell_id} Highlighted")
        self.data_ax.grid(True, alpha=0.3)
        self.data_ax.legend()

        self.data_canvas.draw()
        return True

    def get_random_cell_id(self) -> int | None:
        """Get a random cell ID from the loaded data."""
        if self.main_window is None or self.main_window.raw_data is None:
            return None

        cell_ids = self.main_window.raw_data["cell_id"].unique()
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

"""
Trace viewer widget for displaying cellular time-series data.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QComboBox, QPushButton, QCheckBox, QSpinBox, QTableWidget,
    QTableWidgetItem, QSplitter
)
from PySide6.QtCore import Qt, Signal
import pandas as pd
import numpy as np
from pathlib import Path

# Optional plotting - will gracefully handle if matplotlib not available
try:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    PLOTTING_AVAILABLE = True
except ImportError:
    PLOTTING_AVAILABLE = False

from ....core.data_loading import load_traces_csv


class TraceViewer(QWidget):
    """Widget for viewing and analyzing cellular traces."""
    
    def __init__(self):
        super().__init__()
        self.current_project = None
        self.current_traces = {}  # {fov_idx: DataFrame}
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Controls group
        controls_group = QGroupBox("Trace Analysis Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        # FOV selection
        controls_layout.addWidget(QLabel("FOV:"))
        self.fov_combo = QComboBox()
        self.fov_combo.currentTextChanged.connect(self.on_fov_changed)
        controls_layout.addWidget(self.fov_combo)
        
        controls_layout.addStretch()
        
        # Cell ID selection
        controls_layout.addWidget(QLabel("Cell ID:"))
        self.cell_combo = QComboBox()
        self.cell_combo.currentTextChanged.connect(self.on_cell_changed)
        controls_layout.addWidget(self.cell_combo)
        
        controls_layout.addStretch()
        
        # Data type selection
        controls_layout.addWidget(QLabel("Data:"))
        self.data_combo = QComboBox()
        self.data_combo.addItems([
            "intensity_mean", "intensity_total", "area", 
            "centroid_x", "centroid_y"
        ])
        self.data_combo.currentTextChanged.connect(self.update_plot)
        controls_layout.addWidget(self.data_combo)
        
        # Show all cells checkbox
        self.show_all_checkbox = QCheckBox("Show all cells")
        self.show_all_checkbox.toggled.connect(self.update_plot)
        controls_layout.addWidget(self.show_all_checkbox)
        
        layout.addWidget(controls_group)
        
        # Main content area with splitter
        content_splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(content_splitter)
        
        # Left side - Plot area
        if PLOTTING_AVAILABLE:
            self.setup_plot_area(content_splitter)
        else:
            plot_placeholder = QLabel("Matplotlib not available\\nInstall with: pip install matplotlib")
            plot_placeholder.setAlignment(Qt.AlignCenter)
            content_splitter.addWidget(plot_placeholder)
            
        # Right side - Data table
        self.setup_data_table(content_splitter)
        
        # Set splitter proportions (70% plot, 30% table)
        content_splitter.setSizes([700, 300])
        
        # Initially disable everything until project is loaded
        self.setEnabled(False)
        
    def setup_plot_area(self, parent):
        """Set up the matplotlib plotting area."""
        plot_widget = QWidget()
        plot_layout = QVBoxLayout(plot_widget)
        
        # Create matplotlib figure
        self.figure = Figure(figsize=(10, 6))
        self.canvas = FigureCanvas(self.figure)
        plot_layout.addWidget(self.canvas)
        
        parent.addWidget(plot_widget)
        
    def setup_data_table(self, parent):
        """Set up the data table."""
        table_group = QGroupBox("Trace Data")
        table_layout = QVBoxLayout(table_group)
        
        self.data_table = QTableWidget()
        table_layout.addWidget(self.data_table)
        
        parent.addWidget(table_group)
        
    def load_project(self, project_data: dict):
        """
        Load project data and populate controls.
        
        Args:
            project_data: Project data dictionary
        """
        self.current_project = project_data
        self.current_traces = {}
        
        # Populate FOV combo
        self.fov_combo.clear()
        fov_indices = []
        
        for fov_idx, fov_data in project_data['fov_data'].items():
            if 'traces' in fov_data:
                fov_indices.append(fov_idx)
                
        if fov_indices:
            for fov_idx in sorted(fov_indices):
                self.fov_combo.addItem(f"FOV {fov_idx:04d}", fov_idx)
            self.setEnabled(True)
        else:
            self.fov_combo.addItem("No trace data found")
            self.setEnabled(False)
            
    def on_fov_changed(self):
        """Handle FOV selection change."""
        if not self.current_project:
            return
            
        fov_idx = self.fov_combo.currentData()
        if fov_idx is None:
            return
            
        # Load traces for this FOV
        try:
            fov_data = self.current_project['fov_data'][fov_idx]
            traces_path = fov_data['traces']
            
            df = load_traces_csv(traces_path)
            self.current_traces[fov_idx] = df
            
            # Populate cell combo
            self.cell_combo.clear()
            self.cell_combo.addItem("All cells", None)
            
            cell_ids = sorted(df['cell_id'].unique())
            for cell_id in cell_ids:
                self.cell_combo.addItem(f"Cell {cell_id}", cell_id)
                
            # Update plot and table
            self.update_plot()
            self.update_table()
            
        except Exception as e:
            print(f"Error loading traces: {e}")
            
    def on_cell_changed(self):
        """Handle cell selection change."""
        self.update_plot()
        self.update_table()
        
    def update_plot(self):
        """Update the trace plot."""
        if not PLOTTING_AVAILABLE or not self.current_traces:
            return
            
        fov_idx = self.fov_combo.currentData()
        if fov_idx is None or fov_idx not in self.current_traces:
            return
            
        df = self.current_traces[fov_idx]
        data_type = self.data_combo.currentText()
        cell_id = self.cell_combo.currentData()
        show_all = self.show_all_checkbox.isChecked()
        
        # Clear previous plot
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        
        if show_all or cell_id is None:
            # Plot all cells
            for cid in df['cell_id'].unique():
                cell_data = df[df['cell_id'] == cid]
                ax.plot(cell_data['frame'], cell_data[data_type], 
                       alpha=0.7, label=f'Cell {cid}')
        else:
            # Plot single cell
            cell_data = df[df['cell_id'] == cell_id]
            ax.plot(cell_data['frame'], cell_data[data_type], 'b-', linewidth=2)
            ax.set_title(f'Cell {cell_id} - {data_type}')
            
        ax.set_xlabel('Frame')
        ax.set_ylabel(data_type.replace('_', ' ').title())
        ax.grid(True, alpha=0.3)
        
        if show_all or cell_id is None:
            if len(df['cell_id'].unique()) <= 20:  # Only show legend if not too many cells
                ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
            ax.set_title(f'All Cells - {data_type}')
            
        self.figure.tight_layout()
        self.canvas.draw()
        
    def update_table(self):
        """Update the data table."""
        if not self.current_traces:
            return
            
        fov_idx = self.fov_combo.currentData()
        if fov_idx is None or fov_idx not in self.current_traces:
            return
            
        df = self.current_traces[fov_idx]
        cell_id = self.cell_combo.currentData()
        
        if cell_id is not None:
            # Show data for specific cell
            cell_data = df[df['cell_id'] == cell_id]
        else:
            # Show summary statistics
            cell_data = df.groupby('cell_id').agg({
                'intensity_mean': ['mean', 'std', 'min', 'max'],
                'intensity_total': ['mean', 'std', 'min', 'max'],
                'area': ['mean', 'std', 'min', 'max']
            }).round(2)
            cell_data.columns = ['_'.join(col).strip() for col in cell_data.columns]
            cell_data = cell_data.reset_index()
            
        # Update table
        self.data_table.setRowCount(len(cell_data))
        self.data_table.setColumnCount(len(cell_data.columns))
        self.data_table.setHorizontalHeaderLabels(cell_data.columns.astype(str))
        
        for row in range(len(cell_data)):
            for col in range(len(cell_data.columns)):
                value = cell_data.iloc[row, col]
                item = QTableWidgetItem(str(value))
                self.data_table.setItem(row, col, item)
                
        self.data_table.resizeColumnsToContents()
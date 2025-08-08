"""
Main window for the PyAMA-Qt Visualization application.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction
from pathlib import Path

from .widgets.image_viewer import ImageViewer
from .widgets.simple_folder_loader import SimpleFolderLoader
from ...core.data_loading import discover_processing_results


class VisualizationMainWindow(QMainWindow):
    """Main window for visualization application."""
    
    project_loaded = Signal(dict)  # Emitted when project is loaded
    
    def __init__(self):
        super().__init__()
        self.current_project = None
        self.setup_ui()
        self.setup_statusbar()
        
    def setup_ui(self):
        """Set up the main UI layout."""
        self.setWindowTitle("PyAMA-Qt Visualizer")
        self.setMinimumSize(1200, 800)
        
        # Central widget with splitter layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Main splitter (horizontal)
        main_splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(main_splitter)
        
        # Left panel - Simple folder loader and controls
        self.project_loader = SimpleFolderLoader()
        self.project_loader.project_loaded.connect(self.on_project_loaded)
        self.project_loader.visualization_requested.connect(self.on_visualization_requested)
        main_splitter.addWidget(self.project_loader)
        
        # Right panel - image viewer
        self.image_viewer = ImageViewer()
        main_splitter.addWidget(self.image_viewer)
        
        # Set splitter proportions (30% left, 70% right)
        main_splitter.setSizes([360, 840])
        
    def setup_statusbar(self):
        """Set up the status bar."""
        self.statusbar = self.statusBar()
        self.statusbar.showMessage("Ready - Open a data folder to begin visualization")
        
    def open_project_dialog(self):
        """Open file dialog to select project directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle("Select Data Folder")
        
        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.load_project(Path(selected_dirs[0]))
                
    def load_project(self, project_path: Path):
        """
        Load a PyAMA-Qt processing results project.
        
        Args:
            project_path: Path to the processing results directory
        """
        try:
            self.statusbar.showMessage(f"Loading project: {project_path.name}")
            
            # Discover processing results
            project_data = discover_processing_results(project_path)
            
            self.current_project = project_data
            
            # Show informative status message
            has_project_file = project_data.get('has_project_file', False)
            status = project_data.get('processing_status', 'unknown')
            
            if has_project_file:
                status_msg = f"Project loaded: {project_data['n_fov']} FOVs, Status: {status.title()}"
                if status != 'completed':
                    status_msg += " ⚠️"
            else:
                status_msg = f"Legacy project loaded: {project_data['n_fov']} FOVs (no project file)"
            
            self.project_loaded.emit(project_data)
            
            # Update UI - enable viewer tabs but don't load project data into image viewer yet
            self.setWindowTitle(f"PyAMA-Qt Visualizer - {project_path.name}")
            self.statusbar.showMessage(status_msg)
            
        except Exception as e:
            error_msg = str(e)
            if "No FOV directories found" in error_msg:
                error_msg = f"No data found in {project_path}\\n\\nMake sure you've selected a directory containing FOV subdirectories (fov_0000, fov_0001, etc.)"
            elif "Project file" in error_msg:
                error_msg = f"Project file is corrupted or invalid:\\n{error_msg}\\n\\nTrying to load with legacy file discovery..."
            
            QMessageBox.critical(
                self, 
                "Error Loading Project",
                f"Failed to load project from {project_path}:\\n{error_msg}"
            )
            self.statusbar.showMessage("Error loading project")
            
    def on_project_loaded(self, project_data: dict):
        """Handle project loaded signal from project loader widget."""
        self.current_project = project_data
        
        # Enable viewer tabs but don't load project data yet
        self.image_viewer.setEnabled(True)
        self.setWindowTitle(f"PyAMA-Qt Visualizer - {self.current_project.get('path', {}).name if self.current_project.get('path') else 'Unknown'}")
        
        # Show informative status message
        has_project_file = project_data.get('has_project_file', False)
        status = project_data.get('processing_status', 'unknown')
        
        if has_project_file:
            status_msg = f"Project loaded: {project_data['n_fov']} FOVs, Status: {status.title()}"
            if status != 'completed':
                status_msg += " ⚠️"
        else:
            status_msg = f"Legacy project loaded: {project_data['n_fov']} FOVs (no project file)"
            
        self.statusbar.showMessage(status_msg)
        
    def on_visualization_requested(self, fov_idx: int):
        """Handle visualization requested signal from project loader widget."""
        if self.current_project is not None:
            # Pass project data and specific FOV index to viewer components only when visualization is requested
            self.image_viewer.load_fov_data(self.current_project, fov_idx)
            
    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About PyAMA-Qt Visualizer",
            "PyAMA-Qt Visualizer\\n\\n"
            "Interactive visualization and analysis of microscopy processing results.\\n\\n"
            "Part of the PyAMA-Qt microscopy image analysis suite."
        )
        
    def closeEvent(self, event):
        """Handle application close event."""
        # Could add unsaved changes check here in the future
        event.accept()
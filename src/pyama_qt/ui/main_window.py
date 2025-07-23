from PySide6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, 
                             QStatusBar, QSplitter)
from PySide6.QtCore import Qt, QThread, QObject, Signal
from PySide6.QtGui import QAction
from pathlib import Path

from .widgets.fileloader import FileLoader
from .widgets.workflow import Workflow
from ..services.workflow import WorkflowCoordinator


class WorkflowWorker(QObject):
    """Worker class for running workflow processing in a separate thread."""
    
    finished = Signal(bool, str)  # success, message
    
    def __init__(self, workflow_coordinator, nd2_path, data_info, output_dir, params):
        super().__init__()
        self.workflow_coordinator = workflow_coordinator
        self.nd2_path = nd2_path
        self.data_info = data_info
        self.output_dir = output_dir
        self.params = params
    
    def run_processing(self):
        """Run the workflow processing."""
        try:
            success = self.workflow_coordinator.run_complete_workflow(
                self.nd2_path, self.data_info, self.output_dir, self.params
            )
            
            if success:
                self.finished.emit(True, f"Results saved to {self.output_dir}")
            else:
                self.finished.emit(False, "Workflow failed")
                
        except Exception as e:
            self.finished.emit(False, f"Workflow error: {str(e)}")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyAMA Processing Tool")
        self.setGeometry(100, 100, 800, 500)
        
        self.setup_menu_bar()
        self.setup_ui()
        self.setup_status_bar()
        
    def setup_menu_bar(self):
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("File")
        
        load_nd2_action = QAction("Load ND2 File", self)
        load_nd2_action.triggered.connect(self.load_nd2_file)
        file_menu.addAction(load_nd2_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Help menu
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        
        # Create splitter for file loading and processing sections
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # File loading section
        self.file_loader = FileLoader()
        splitter.addWidget(self.file_loader)
        
        # Processing workflow
        self.workflow_tab = Workflow()
        splitter.addWidget(self.workflow_tab)
        
        # Set splitter proportions (file loader left, workflow right)
        splitter.setSizes([350, 650])
        
        main_layout.addWidget(splitter)
        
        # Initialize workflow coordinator
        self.workflow_coordinator = WorkflowCoordinator(self)
        self.setup_workflow_connections()
        
        # Connect signals
        self.file_loader.data_loaded.connect(self.on_data_loaded)
        self.file_loader.status_message.connect(self.update_status)
        self.workflow_tab.process_requested.connect(self.start_workflow_processing)
        
    def setup_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
    def load_nd2_file(self):
        self.file_loader.select_nd2_file()
        
        
    def show_about(self):
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.about(self, "About PyAMA Processing Tool", 
                         "PyAMA Processing Tool v0.1.0\\n\\n"
                         "Image processing tools for microscopy data\\n"
                         "Features binarization and background correction")
        
    def on_data_loaded(self, data_info):
        """Handle when data is successfully loaded"""
        self.status_bar.showMessage(f"Loaded: {data_info['filepath']}")
        
        # Enable processing workflow
        self.workflow_tab.set_data_available(True, data_info)
        
    def setup_workflow_connections(self):
        """Connect workflow coordinator signals to UI updates"""
        services = self.workflow_coordinator.get_all_services()
        
        for service in services:
            service.progress_updated.connect(self.workflow_tab.update_progress)
            service.status_updated.connect(self.update_workflow_status)
            service.step_completed.connect(self.on_step_completed)
            service.error_occurred.connect(self.on_workflow_error)
    
    def start_workflow_processing(self, params):
        """Start workflow processing in a separate thread"""
        # Extract parameters
        nd2_path = params['data_info']['filepath']
        data_info = params['data_info']  
        output_dir = Path(params['output_dir'])
        
        # Map step names to signal light names
        self.step_name_mapping = {
            'Binarization': 'segmentation',
            'Background Correction': 'background_correction',
            'Pickle Maximum Bounding Box': 'bounding_box'
        }
        
        # Create worker and thread
        self.processing_thread = QThread()
        self.workflow_worker = WorkflowWorker(
            self.workflow_coordinator, nd2_path, data_info, output_dir, params
        )
        
        # Move worker to thread
        self.workflow_worker.moveToThread(self.processing_thread)
        
        # Connect signals
        self.processing_thread.started.connect(self.workflow_worker.run_processing)
        self.workflow_worker.finished.connect(self.on_processing_finished)
        self.workflow_worker.finished.connect(self.processing_thread.quit)
        self.workflow_worker.finished.connect(self.workflow_worker.deleteLater)
        self.processing_thread.finished.connect(self.processing_thread.deleteLater)
        
        # Start processing
        self.processing_thread.start()
        
        # Update UI
        self.workflow_tab.reset_signal_lights()
        self.update_status("Starting workflow processing...")
        
    def on_processing_finished(self, success, message):
        """Handle when workflow processing finishes"""
        self.workflow_tab.processing_finished(success, message)
        if success:
            self.update_status("Workflow completed successfully")
        else:
            self.update_status(f"Workflow failed: {message}")
    
    def update_workflow_status(self, message):
        """Update workflow status and main status bar"""
        self.workflow_tab.log_area.append(message)
        self.update_status(message)
        
    def on_step_completed(self, step_name):
        """Handle when a processing step completes"""
        # Map service step names to UI signal light names
        ui_step_name = self.step_name_mapping.get(step_name, step_name.lower().replace(' ', '_'))
        self.workflow_tab.set_signal_light_status(ui_step_name, 'completed')
        self.workflow_tab.log_area.append(f"✓ {step_name} completed successfully")
        
    def on_workflow_error(self, error_message):
        """Handle workflow processing errors"""
        self.workflow_tab.processing_error(error_message)
        self.update_status(f"Error: {error_message}")

    def update_status(self, message):
        """Update status bar message"""
        self.status_bar.showMessage(message)
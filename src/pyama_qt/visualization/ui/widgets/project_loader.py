"""
Project loader widget for the visualization application.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, 
    QFileDialog, QTreeWidget, QTreeWidgetItem, QMessageBox, QListWidget, 
    QListWidgetItem, QSplitter, QFrame
)
from PySide6.QtCore import Signal, Qt
from pathlib import Path
from typing_extensions import TypedDict

from ....core.data_loading import discover_processing_results


class ProjectInfo(TypedDict):
    """Type definition for project information in the list"""
    name: str
    path: Path
    data: dict
    is_master: bool


class ProjectLoader(QWidget):
    """Widget for loading and displaying project information."""
    
    project_loaded = Signal(dict)  # Emitted when project is successfully loaded
    project_selected = Signal(dict)  # Emitted when a project is selected from the list
    
    def __init__(self):
        super().__init__()
        self.projects: list[ProjectInfo] = []
        self.current_project = None
        self.is_master_mode = False  # True when master project is loaded
        self.setup_ui()
        
    def setup_ui(self):
        """Set up the UI layout."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Project loading controls
        controls_group = QGroupBox("Load Projects")
        controls_layout = QVBoxLayout(controls_group)
        
        # Load buttons
        buttons_layout = QHBoxLayout()
        
        self.load_master_button = QPushButton("Load Master Project...")
        self.load_master_button.clicked.connect(self.load_master_project_dialog)
        self.load_master_button.setToolTip("Load a master project file that contains multiple FOVs")
        buttons_layout.addWidget(self.load_master_button)
        
        self.add_project_button = QPushButton("Add Individual Project...")
        self.add_project_button.clicked.connect(self.add_individual_project_dialog)
        self.add_project_button.setToolTip("Add an individual project directory to the list")
        buttons_layout.addWidget(self.add_project_button)
        
        self.clear_button = QPushButton("Clear All")
        self.clear_button.clicked.connect(self.clear_all_projects)
        self.clear_button.setToolTip("Clear all loaded projects")
        buttons_layout.addWidget(self.clear_button)
        
        controls_layout.addLayout(buttons_layout)
        
        # Mode indicator
        self.mode_label = QLabel("Mode: Individual Projects")
        self.mode_label.setStyleSheet("font-weight: bold; color: #666;")
        controls_layout.addWidget(self.mode_label)
        
        layout.addWidget(controls_group)
        
        # Main content splitter
        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)
        
        # Left side - Project list
        list_frame = QFrame()
        list_layout = QVBoxLayout(list_frame)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QLabel("Projects:")
        list_label.setStyleSheet("font-weight: bold;")
        list_layout.addWidget(list_label)
        
        self.project_list = QListWidget()
        self.project_list.currentItemChanged.connect(self.on_project_selection_changed)
        self.project_list.setMinimumWidth(200)
        list_layout.addWidget(self.project_list)
        
        splitter.addWidget(list_frame)
        
        # Right side - Project details
        details_frame = QFrame()
        details_layout = QVBoxLayout(details_frame)
        details_layout.setContentsMargins(0, 0, 0, 0)
        
        # Project info group
        info_group = QGroupBox("Project Information")
        info_layout = QVBoxLayout(info_group)
        
        self.info_tree = QTreeWidget()
        self.info_tree.setHeaderLabel("Details")
        self.info_tree.setMaximumHeight(250)
        info_layout.addWidget(self.info_tree)
        
        details_layout.addWidget(info_group)
        
        # Data overview group
        data_group = QGroupBox("Available Data")
        data_layout = QVBoxLayout(data_group)
        
        self.data_tree = QTreeWidget()
        self.data_tree.setHeaderLabels(["FOV", "Data Type", "File"])
        data_layout.addWidget(self.data_tree)
        
        details_layout.addWidget(data_group)
        
        splitter.addWidget(details_frame)
        
        # Set splitter proportions
        splitter.setStretchFactor(0, 0)  # Fixed width for project list
        splitter.setStretchFactor(1, 1)  # Expandable for details
        
        # Initially disable details
        info_group.setEnabled(False)
        data_group.setEnabled(False)
        
        self.info_group = info_group
        self.data_group = data_group
        
    def load_master_project_dialog(self):
        """Open dialog to select master project directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle("Select Master Project Directory")
        
        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.load_master_project(Path(selected_dirs[0]))
                
    def add_individual_project_dialog(self):
        """Open dialog to add individual project directory."""
        if self.is_master_mode:
            QMessageBox.information(
                self,
                "Master Mode Active",
                "Cannot add individual projects when a master project is loaded. Clear all projects first."
            )
            return
            
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.Directory)
        dialog.setWindowTitle("Add Individual Project Directory")
        
        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                self.add_individual_project(Path(selected_dirs[0]))
                
    def load_master_project(self, project_path: Path):
        """
        Load master project from directory.
        
        Args:
            project_path: Path to the master project directory
        """
        try:
            # Clear existing projects
            self.clear_all_projects()
            
            # Discover processing results
            project_data = discover_processing_results(project_path)
            
            # Check if it's actually a master project
            if not project_data.get('has_master_project_file', False):
                QMessageBox.warning(
                    self,
                    "Not a Master Project",
                    f"The selected directory does not contain a master project file. Use 'Add Individual Project' instead."
                )
                return
            
            # Set master mode
            self.is_master_mode = True
            self.update_ui_mode()
            
            # Create projects from FOVs in master project
            master_metadata = project_data.get('master_project_metadata', {})
            fovs_data = master_metadata.get('fovs', {})
            
            for fov_key, fov_info in sorted(fovs_data.items()):
                fov_idx = fov_info['index']
                
                # Create a project info for each FOV
                project_info: ProjectInfo = {
                    'name': f"{project_path.name} - {fov_key}",
                    'path': project_path,
                    'data': {
                        **project_data,
                        # Filter fov_data to only include this FOV
                        'fov_data': {fov_idx: project_data['fov_data'].get(fov_idx, {})},
                        'current_fov': fov_idx,
                        'master_fov_info': fov_info
                    },
                    'is_master': True
                }
                
                self.projects.append(project_info)
                
            self.update_project_list()
            
            # Select first project if available
            if self.projects:
                self.project_list.setCurrentRow(0)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Loading Master Project", 
                f"Failed to load master project from {project_path}:\\n{str(e)}"
            )
            
    def add_individual_project(self, project_path: Path):
        """
        Add individual project to the list.
        
        Args:
            project_path: Path to the processing results directory
        """
        try:
            # Check if already added
            for existing_project in self.projects:
                if existing_project['path'] == project_path:
                    QMessageBox.information(
                        self,
                        "Project Already Added",
                        f"The project from {project_path} is already in the list."
                    )
                    return
            
            # Discover processing results
            project_data = discover_processing_results(project_path)
            
            # Create project info
            project_info: ProjectInfo = {
                'name': project_path.name,
                'path': project_path,
                'data': project_data,
                'is_master': False
            }
            
            self.projects.append(project_info)
            self.update_project_list()
            
            # Select the newly added project
            self.project_list.setCurrentRow(len(self.projects) - 1)
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Error Adding Project", 
                f"Failed to add project from {project_path}:\\n{str(e)}"
            )
            
    def clear_all_projects(self):
        """Clear all loaded projects."""
        self.projects.clear()
        self.current_project = None
        self.is_master_mode = False
        self.update_ui_mode()
        self.update_project_list()
        
        # Clear displays
        self.info_tree.clear()
        self.data_tree.clear()
        self.info_group.setEnabled(False)
        self.data_group.setEnabled(False)
        
    def update_ui_mode(self):
        """Update UI based on current mode."""
        if self.is_master_mode:
            self.mode_label.setText("Mode: Master Project")
            self.mode_label.setStyleSheet("font-weight: bold; color: #0066cc;")
            self.add_project_button.setEnabled(False)
            self.load_master_button.setEnabled(False)
        else:
            self.mode_label.setText("Mode: Individual Projects")
            self.mode_label.setStyleSheet("font-weight: bold; color: #666;")
            self.add_project_button.setEnabled(True)
            self.load_master_button.setEnabled(True)
            
    def update_project_list(self):
        """Update the project list widget."""
        self.project_list.clear()
        
        for project_info in self.projects:
            item = QListWidgetItem(project_info['name'])
            
            # Set item data for easy retrieval
            item.setData(Qt.UserRole, project_info)
            
            # Add status indicator
            project_data = project_info['data']
            status = project_data.get('processing_status', 'unknown')
            
            if status == 'completed':
                item.setText(f"✅ {project_info['name']}")
            elif status == 'failed':
                item.setText(f"❌ {project_info['name']}")
            else:
                item.setText(f"⏳ {project_info['name']}")
                
            self.project_list.addItem(item)
            
    def on_project_selection_changed(self, current_item, previous_item):
        """Handle project selection change."""
        if current_item is None:
            self.current_project = None
            self.info_group.setEnabled(False)
            self.data_group.setEnabled(False)
            return
            
        # Get project info from item data
        project_info = current_item.data(Qt.UserRole)
        project_data = project_info['data']
        
        self.current_project = project_data
        self.update_project_display(project_data)
        
        # Enable displays
        self.info_group.setEnabled(True)
        self.data_group.setEnabled(True)
        
        # Emit signals
        self.project_selected.emit(project_data)
        self.project_loaded.emit(project_data)
            
    def update_project_display(self, project_data: dict):
        """
        Update the project information display.
        
        Args:
            project_data: Project data dictionary
        """
        # Extract project info
        project_path = project_data['project_path']
        has_project_file = project_data.get('has_project_file', False)
        has_master_project_file = project_data.get('has_master_project_file', False)
        current_fov = project_data.get('current_fov')  # FOV index for master project mode
        
        # Update info tree
        self.info_tree.clear()
        
        # Basic info
        basic_info = QTreeWidgetItem(["Basic Information"])
        basic_info.addChild(QTreeWidgetItem([f"Project Directory: {project_path.name}"]))
        
        if current_fov is not None:
            # Master project mode - show FOV-specific info
            basic_info.addChild(QTreeWidgetItem([f"Current FOV: {current_fov:04d}"]))
            basic_info.addChild(QTreeWidgetItem([f"Total FOVs in Master: {len(project_data.get('master_project_metadata', {}).get('fovs', {}))}"]))
        else:
            # Individual project mode
            basic_info.addChild(QTreeWidgetItem([f"Fields of View: {project_data['n_fov']}"]))
            
        if project_data['nd2_file']:
            basic_info.addChild(QTreeWidgetItem([f"Source File: {project_data['nd2_file']}"]))
        basic_info.addChild(QTreeWidgetItem([f"Has Project File: {'Yes' if has_project_file else 'No'}"])) 
        basic_info.addChild(QTreeWidgetItem([f"Has Master Project: {'Yes' if has_master_project_file else 'No'}"]))
        self.info_tree.addTopLevelItem(basic_info)
        basic_info.setExpanded(True)
        
        # File validation (if project file available)
        if has_project_file and 'project_metadata' in project_data:
            from ....core.project import validate_project_files
            
            validation_results = validate_project_files(project_data['project_metadata'])
            missing_files = [path for path, exists in validation_results.items() if not exists]
            
            if missing_files:
                validation_info = QTreeWidgetItem([f"⚠️ File Validation ({len(missing_files)} missing)"])
                for missing_file in missing_files[:5]:  # Show first 5 missing files
                    validation_info.addChild(QTreeWidgetItem([f"Missing: {Path(missing_file).name}"]))
                if len(missing_files) > 5:
                    validation_info.addChild(QTreeWidgetItem([f"... and {len(missing_files) - 5} more"]))
                self.info_tree.addTopLevelItem(validation_info)
                validation_info.setExpanded(True)
            else:
                validation_info = QTreeWidgetItem(["✅ All Files Present"])
                self.info_tree.addTopLevelItem(validation_info)
        
        # Processing info - handle both master and individual modes
        if current_fov is not None and 'master_fov_info' in project_data:
            # Master project mode - show FOV-specific processing info
            fov_info = project_data['master_fov_info']
            processing_info = QTreeWidgetItem([f"FOV {current_fov:04d} Processing"])
            
            # FOV status and timing
            status = fov_info.get('status', 'unknown')
            processing_info.addChild(QTreeWidgetItem([f"Status: {status.title()}"]))
            
            if fov_info.get('started'):
                processing_info.addChild(QTreeWidgetItem([f"Started: {fov_info['started'][:19].replace('T', ' ')}"]))
            if fov_info.get('completed'):
                processing_info.addChild(QTreeWidgetItem([f"Completed: {fov_info['completed'][:19].replace('T', ' ')}"]))
            if fov_info.get('duration_seconds'):
                duration = fov_info['duration_seconds']
                processing_info.addChild(QTreeWidgetItem([f"Duration: {duration:.1f} seconds"]))
            
            # Processing parameters from master project
            params = project_data.get('processing_parameters', {})
            if params:
                params_item = QTreeWidgetItem(["Parameters"])
                for param, value in params.items():
                    params_item.addChild(QTreeWidgetItem([f"{param.replace('_', ' ').title()}: {value}"]))
                processing_info.addChild(params_item)
                params_item.setExpanded(True)
            
            self.info_tree.addTopLevelItem(processing_info)
            processing_info.setExpanded(True)
            
        elif has_master_project_file and 'master_project_metadata' in project_data:
            metadata = project_data['master_project_metadata']
            processing_info = QTreeWidgetItem(["Master Processing Information"])
            
            # Processing status and timing
            proc_data = metadata.get('processing', {})
            processing_info.addChild(QTreeWidgetItem([f"Status: {proc_data.get('status', 'unknown').title()}"]))
            processing_info.addChild(QTreeWidgetItem([f"Total FOVs: {proc_data.get('total_fovs', 0)}"]))
            processing_info.addChild(QTreeWidgetItem([f"Completed FOVs: {proc_data.get('completed_fovs', 0)}"]))
            if proc_data.get('failed_fovs', 0) > 0:
                processing_info.addChild(QTreeWidgetItem([f"Failed FOVs: {proc_data.get('failed_fovs', 0)}"]))
            
            if proc_data.get('started'):
                processing_info.addChild(QTreeWidgetItem([f"Started: {proc_data['started'][:19].replace('T', ' ')}"]))
            if proc_data.get('completed'):
                processing_info.addChild(QTreeWidgetItem([f"Completed: {proc_data['completed'][:19].replace('T', ' ')}"]))
            if proc_data.get('duration_seconds'):
                duration = proc_data['duration_seconds']
                processing_info.addChild(QTreeWidgetItem([f"Total Duration: {duration:.1f} seconds"]))
            
            # Processing parameters
            params = project_data.get('processing_parameters', {})
            if params:
                params_item = QTreeWidgetItem(["Parameters"])
                for param, value in params.items():
                    params_item.addChild(QTreeWidgetItem([f"{param.replace('_', ' ').title()}: {value}"]))
                processing_info.addChild(params_item)
                params_item.setExpanded(True)
            
            # FOV status overview
            fovs_data = metadata.get('fovs', {})
            if fovs_data:
                fovs_item = QTreeWidgetItem(["FOV Status"])
                for fov_key, fov_info in sorted(fovs_data.items()):
                    status = fov_info.get('status', 'unknown')
                    duration = fov_info.get('duration_seconds')
                    fov_text = f"{fov_key}: {status.title()}"
                    if duration:
                        fov_text += f" ({duration:.1f}s)"
                    status_emoji = "✅" if status == "completed" else "❌" if status == "failed" else "⏳"
                    fov_text = f"{status_emoji} {fov_text}"
                    fovs_item.addChild(QTreeWidgetItem([fov_text]))
                processing_info.addChild(fovs_item)
                fovs_item.setExpanded(True)
            
            self.info_tree.addTopLevelItem(processing_info)
            processing_info.setExpanded(True)
            
        elif has_project_file and 'project_metadata' in project_data:
            metadata = project_data['project_metadata']
            processing_info = QTreeWidgetItem(["Processing Information"])
            
            # Processing status and timing
            proc_data = metadata.get('processing', {})
            processing_info.addChild(QTreeWidgetItem([f"Status: {proc_data.get('status', 'unknown').title()}"]))
            
            if proc_data.get('started'):
                processing_info.addChild(QTreeWidgetItem([f"Started: {proc_data['started'][:19].replace('T', ' ')}"]))
            if proc_data.get('completed'):
                processing_info.addChild(QTreeWidgetItem([f"Completed: {proc_data['completed'][:19].replace('T', ' ')}"]))
            if proc_data.get('duration_seconds'):
                duration = proc_data['duration_seconds']
                processing_info.addChild(QTreeWidgetItem([f"Duration: {duration:.1f} seconds"]))
            
            # Processing parameters
            params = project_data.get('processing_parameters', {})
            if params:
                params_item = QTreeWidgetItem(["Parameters"])
                for param, value in params.items():
                    params_item.addChild(QTreeWidgetItem([f"{param.replace('_', ' ').title()}: {value}"]))
                processing_info.addChild(params_item)
                params_item.setExpanded(True)
            
            # Processing steps
            steps = proc_data.get('steps', {})
            if steps:
                steps_item = QTreeWidgetItem(["Processing Steps"])
                for step_name, step_data in steps.items():
                    status = step_data.get('status', 'unknown')
                    duration = step_data.get('duration_seconds')
                    step_text = f"{step_name.replace('_', ' ').title()}: {status.title()}"
                    if duration:
                        step_text += f" ({duration:.1f}s)"
                    steps_item.addChild(QTreeWidgetItem([step_text]))
                processing_info.addChild(steps_item)
                steps_item.setExpanded(True)
            
            self.info_tree.addTopLevelItem(processing_info)
            processing_info.setExpanded(True)
        
        # Data types available
        all_data_types = set()
        for fov_data in project_data['fov_data'].values():
            all_data_types.update(fov_data.keys())
        
        data_types_info = QTreeWidgetItem(["Available Data Types"])
        for data_type in sorted(all_data_types):
            data_types_info.addChild(QTreeWidgetItem([data_type.replace('_', ' ').title()]))
        self.info_tree.addTopLevelItem(data_types_info)
        data_types_info.setExpanded(True)
        
        # Update data tree
        self.data_tree.clear()
        
        for fov_idx in sorted(project_data['fov_data'].keys()):
            fov_data = project_data['fov_data'][fov_idx]
            
            # Show FOV status
            fov_status = ""
            if current_fov is not None and 'master_fov_info' in project_data:
                # Master project mode - get status from master FOV info
                status = project_data['master_fov_info'].get('status', 'unknown')
                if status == 'completed':
                    fov_status = " ✅"
                elif status == 'failed':
                    fov_status = " ❌"
            elif has_project_file and 'project_metadata' in project_data:
                # Individual project mode - get status from project metadata
                fov_key = f"fov_{fov_idx:04d}"
                fov_info = project_data['project_metadata']['output'].get(fov_key, {})
                status = fov_info.get('status', 'unknown')
                if status == 'completed':
                    fov_status = " ✅"
                elif status == 'failed':
                    fov_status = " ❌"
            
            fov_item = QTreeWidgetItem([f"FOV {fov_idx:04d}{fov_status}", "", ""])
            
            for data_type, file_path in fov_data.items():
                data_item = QTreeWidgetItem(["", data_type.replace('_', ' ').title(), file_path.name])
                fov_item.addChild(data_item)
                
            self.data_tree.addTopLevelItem(fov_item)
            fov_item.setExpanded(True)
            
        # Resize columns
        self.data_tree.resizeColumnToContents(0)
        self.data_tree.resizeColumnToContents(1)
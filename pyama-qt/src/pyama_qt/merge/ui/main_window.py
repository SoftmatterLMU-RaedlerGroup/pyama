"""
Main window for the PyAMA merge application.

This module provides the main application window that coordinates FOV discovery,
sample grouping, and data export functionality.
"""

import logging
from pathlib import Path
from typing import List, Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QSplitter, QGroupBox, QStatusBar, QMenuBar, QMenu
)
from PySide6.QtCore import Qt, Signal, Slot, QThread, QTimer
from PySide6.QtGui import QFont, QAction

from ..services.discovery import FOVDiscoveryService, FOVInfo
from ..services.merge import MergeService, SampleGroup, MergeConfiguration
from .widgets.fov_table import FOVTable
from .widgets.sample_table import SampleTable
from .widgets.statistics import StatisticsWidget
from pyama_qt.utils.logging_config import get_logger, setup_logging

# Initialize logging for merge module
setup_logging(use_qt_handler=True, module="merge")
logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """
    Main window for the PyAMA merge application.
    
    Provides a complete interface for:
    - Selecting processing output directories
    - Viewing discovered FOV information
    - Creating sample groups with FOV assignments
    - Viewing sample statistics
    - Exporting merged data (implemented in later tasks)
    """
    
    # Signals
    directory_selected = Signal(Path)  # Emitted when a directory is selected
    fovs_discovered = Signal(list)     # Emitted when FOVs are discovered
    
    def __init__(self):
        super().__init__()
        self.logger = get_logger(__name__)
        
        # Services
        self.discovery_service = FOVDiscoveryService()
        self.merge_service = MergeService()
        
        # Data storage
        self.current_directory = None
        self.discovered_fovs = []
        
        # Discovery thread management
        self.discovery_thread = None
        
        self.setup_ui()
        self.setup_menu_bar()
        self.connect_signals()
        
        # Set window properties
        self.setWindowTitle("PyAMA-Qt Merge Application")
        self.resize(1000, 700)
        
        # Set initial status
        self.status_bar.showMessage("Ready - Select a processing output directory to begin")
        
    def setup_ui(self):
        """Set up the user interface layout."""
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Main layout
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # Directory selection section
        self.setup_directory_section(main_layout)
        
        # Main content area with splitter
        self.setup_content_area(main_layout)
        
        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
    def setup_menu_bar(self):
        """Set up the menu bar with configuration options."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        # Save configuration action
        self.save_config_action = QAction("&Save Configuration...", self)
        self.save_config_action.setShortcut("Ctrl+S")
        self.save_config_action.setStatusTip("Save current sample grouping configuration")
        self.save_config_action.setEnabled(False)  # Disabled until samples are defined
        file_menu.addAction(self.save_config_action)
        
        # Load configuration action
        self.load_config_action = QAction("&Load Configuration...", self)
        self.load_config_action.setShortcut("Ctrl+O")
        self.load_config_action.setStatusTip("Load sample grouping configuration")
        file_menu.addAction(self.load_config_action)
        
        # Separator
        file_menu.addSeparator()
        
        # Exit action
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.setStatusTip("Exit application")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
    def setup_directory_section(self, parent_layout):
        """Set up the directory selection section."""
        # Directory selection group
        dir_group = QGroupBox("Processing Output Directory")
        dir_layout = QHBoxLayout(dir_group)
        
        # Directory path label
        self.directory_label = QLabel("No directory selected")
        self.directory_label.setStyleSheet("padding: 5px; background-color: #f0f0f0; border: 1px solid #ccc;")
        dir_layout.addWidget(self.directory_label, 1)
        
        # Browse button
        self.browse_button = QPushButton("Browse...")
        self.browse_button.setMinimumWidth(100)
        dir_layout.addWidget(self.browse_button)
        
        parent_layout.addWidget(dir_group)
        
    def setup_export_section(self, parent_layout):
        """Set up the export section with buttons."""
        # Export section group
        export_group = QGroupBox("Export")
        export_layout = QHBoxLayout(export_group)
        
        # Export button
        self.export_button = QPushButton("Export Samples")
        self.export_button.setMinimumWidth(120)
        self.export_button.setEnabled(False)  # Disabled until samples are ready
        export_layout.addWidget(self.export_button)
        
        # Add stretch to push button to the left
        export_layout.addStretch()
        
        parent_layout.addWidget(export_group)
        
    def setup_content_area(self, parent_layout):
        """Set up the main content area with widgets."""
        # Create splitter for resizable sections
        splitter = QSplitter(Qt.Orientation.Vertical)
        
        # FOV information section
        fov_group = QGroupBox("FOV Information")
        fov_layout = QVBoxLayout(fov_group)
        
        self.fov_table = FOVTable()
        fov_layout.addWidget(self.fov_table)
        
        splitter.addWidget(fov_group)
        
        # Sample grouping section
        sample_group = QGroupBox("Sample Grouping")
        sample_layout = QVBoxLayout(sample_group)
        
        self.sample_table = SampleTable()
        sample_layout.addWidget(self.sample_table)
        
        splitter.addWidget(sample_group)
        
        # Statistics section
        stats_group = QGroupBox("Sample Statistics")
        stats_layout = QVBoxLayout(stats_group)
        
        self.statistics_widget = StatisticsWidget()
        stats_layout.addWidget(self.statistics_widget)
        
        splitter.addWidget(stats_group)
        
        # Set splitter proportions (FOV: 30%, Sample: 40%, Stats: 30%)
        splitter.setSizes([300, 400, 300])
        
        parent_layout.addWidget(splitter, 1)
        
        # Export section
        self.setup_export_section(parent_layout)
        
    def connect_signals(self):
        """Connect widget signals and slots."""
        # Directory selection
        self.browse_button.clicked.connect(self.select_directory)
        self.directory_selected.connect(self.on_directory_selected)
        
        # FOV discovery
        self.fovs_discovered.connect(self.on_fovs_discovered)
        
        # Sample table signals
        self.sample_table.sample_selection_changed.connect(self.statistics_widget.update_sample_statistics)
        self.sample_table.samples_changed.connect(self.on_samples_changed)
        
        # Export functionality
        self.export_button.clicked.connect(self.export_samples)
        
        # Configuration menu actions
        self.save_config_action.triggered.connect(self.save_configuration)
        self.load_config_action.triggered.connect(self.load_configuration)
        
    @Slot()
    def select_directory(self):
        """Open file dialog to select processing output directory."""
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Processing Output Directory")
        
        # Set initial directory if we have one
        if self.current_directory:
            dialog.setDirectory(str(self.current_directory))
        
        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                directory_path = Path(selected_dirs[0])
                self.directory_selected.emit(directory_path)
                
    @Slot(Path)
    def on_directory_selected(self, directory_path: Path):
        """
        Handle directory selection and start FOV discovery.
        
        Args:
            directory_path: Selected directory path
        """
        self.logger.info(f"Directory selected: {directory_path}")
        
        # Update UI
        self.current_directory = directory_path
        self.directory_label.setText(str(directory_path))
        
        # Clear existing data
        self.clear_all_data()
        
        # Start FOV discovery
        self.start_fov_discovery(directory_path)
        
    def start_fov_discovery(self, directory_path: Path):
        """
        Start FOV discovery in a separate thread.
        
        Args:
            directory_path: Directory to search for FOV files
        """
        # Disable browse button during discovery
        self.browse_button.setEnabled(False)
        self.status_bar.showMessage("Discovering FOV files...")
        
        # Use QTimer for simple async operation
        QTimer.singleShot(100, lambda: self.perform_fov_discovery(directory_path))
        
    def perform_fov_discovery(self, directory_path: Path):
        """
        Perform FOV discovery and update UI.
        
        Args:
            directory_path: Directory to search for FOV files
        """
        try:
            # Discover FOV files
            fov_infos = self.discovery_service.discover_fov_files(directory_path)
            
            # Emit signal with results
            self.fovs_discovered.emit(fov_infos)
            
        except Exception as e:
            self.logger.error(f"FOV discovery failed: {e}")
            self.show_error("FOV Discovery Failed", 
                          f"Failed to discover FOV files in the selected directory:\n\n{str(e)}")
        finally:
            # Re-enable browse button
            self.browse_button.setEnabled(True)
            
    @Slot(list)
    def on_fovs_discovered(self, fov_infos: List[FOVInfo]):
        """
        Handle successful FOV discovery.
        
        Args:
            fov_infos: List of discovered FOVInfo objects
        """
        self.logger.info(f"Discovered {len(fov_infos)} FOV files")
        
        # Store discovered FOVs
        self.discovered_fovs = fov_infos
        
        # Update FOV table
        self.fov_table.populate_from_fov_list(fov_infos)
        
        # Update sample table with available FOVs
        fov_indices = [fov.index for fov in fov_infos]
        self.sample_table.set_available_fovs(fov_indices)
        
        # Update statistics widget
        self.statistics_widget.set_available_fovs(fov_infos)
        
        # Update status bar
        total_cells = sum(fov.cell_count for fov in fov_infos)
        self.status_bar.showMessage(
            f"Discovered {len(fov_infos)} FOVs with {total_cells} total cells - Ready to create sample groups"
        )
        
        # Log summary statistics
        stats = self.discovery_service.get_summary_stats(fov_infos)
        self.logger.info(f"FOV discovery summary: {stats}")
        
        # Update export button state
        self.update_export_button_state()
        
        # Update configuration menu state
        self.update_configuration_menu_state()
        
    @Slot()
    def on_samples_changed(self):
        """Handle changes to sample definitions."""
        sample_groups = self.sample_table.get_sample_groups()
        self.logger.debug(f"Sample groups updated: {len(sample_groups)} samples defined")
        
        # Update export button state based on sample validation
        self.update_export_button_state()
        
        # Update configuration menu state
        self.update_configuration_menu_state()
        
    def clear_all_data(self):
        """Clear all data from the interface."""
        self.discovered_fovs = []
        self.fov_table.clear_table()
        self.sample_table.clear_table()
        self.statistics_widget.clear_statistics()
        
        self.logger.debug("All data cleared from interface")
        
    def show_error(self, title: str, message: str):
        """
        Show an error message dialog.
        
        Args:
            title: Dialog title
            message: Error message
        """
        QMessageBox.critical(self, title, message)
        
    def show_info(self, title: str, message: str):
        """
        Show an information message dialog.
        
        Args:
            title: Dialog title
            message: Information message
        """
        QMessageBox.information(self, title, message)
        
    def show_warning(self, title: str, message: str):
        """
        Show a warning message dialog.
        
        Args:
            title: Dialog title
            message: Warning message
        """
        QMessageBox.warning(self, title, message)
        
    def update_export_button_state(self):
        """Update the export button enabled state based on current data."""
        # Enable export button if we have FOVs and valid samples
        has_fovs = bool(self.discovered_fovs)
        sample_groups = self.sample_table.get_sample_groups()
        has_valid_samples = bool(sample_groups)
        
        # Additional validation - check that all samples have FOVs assigned
        all_samples_have_fovs = all(sg.resolved_fovs for sg in sample_groups) if sample_groups else False
        
        export_ready = has_fovs and has_valid_samples and all_samples_have_fovs
        self.export_button.setEnabled(export_ready)
        
        # Update status message
        if not has_fovs:
            status_msg = "Select a directory with FOV files to enable export"
        elif not has_valid_samples:
            status_msg = "Define sample groups to enable export"
        elif not all_samples_have_fovs:
            status_msg = "All samples must have assigned FOVs to enable export"
        else:
            total_samples = len(sample_groups)
            total_fovs = sum(len(sg.resolved_fovs) for sg in sample_groups)
            status_msg = f"Ready to export {total_samples} samples with {total_fovs} FOVs"
            
        self.status_bar.showMessage(status_msg)
        
    @Slot()
    def export_samples(self):
        """Export all defined samples to CSV files."""
        try:
            # Get sample groups
            sample_groups = self.sample_table.get_sample_groups()
            
            if not sample_groups:
                self.show_warning("Export Error", "No samples defined for export.")
                return
                
            # Validate samples before export
            validation_errors = self.validate_samples_for_export(sample_groups)
            if validation_errors:
                error_msg = "Cannot export due to validation errors:\n\n" + "\n".join(validation_errors)
                self.show_error("Export Validation Failed", error_msg)
                return
                
            # Select output directory
            output_dir = self.select_export_directory()
            if not output_dir:
                return  # User cancelled
                
            # Disable export button during operation
            self.export_button.setEnabled(False)
            self.status_bar.showMessage("Exporting samples...")
            
            # Perform export
            self.perform_sample_export(sample_groups, output_dir)
            
        except Exception as e:
            self.logger.error(f"Export failed: {e}")
            self.show_error("Export Failed", f"An error occurred during export:\n\n{str(e)}")
        finally:
            # Re-enable export button
            self.update_export_button_state()
            
    def validate_samples_for_export(self, sample_groups: List[SampleGroup]) -> List[str]:
        """
        Validate sample groups before export.
        
        Args:
            sample_groups: List of sample groups to validate
            
        Returns:
            List of validation error messages
        """
        errors = []
        
        # Check that all samples have assigned FOVs
        empty_samples = [sg.name for sg in sample_groups if not sg.resolved_fovs]
        if empty_samples:
            errors.append(f"Samples with no assigned FOVs: {', '.join(empty_samples)}")
            
        # Use merge service validation
        available_fov_indices = [fov.index for fov in self.discovered_fovs]
        merge_errors = self.merge_service.validate_sample_groups(sample_groups, available_fov_indices)
        errors.extend(merge_errors)
        
        # Check that all referenced FOVs exist in discovered data
        fov_file_map = {fov.index: fov.file_path for fov in self.discovered_fovs}
        for sample_group in sample_groups:
            missing_fovs = [fov_idx for fov_idx in sample_group.resolved_fovs if fov_idx not in fov_file_map]
            if missing_fovs:
                errors.append(f"Sample '{sample_group.name}' references missing FOVs: {missing_fovs}")
                
        return errors
        
    def select_export_directory(self) -> Optional[Path]:
        """
        Select directory for export output.
        
        Returns:
            Selected directory path or None if cancelled
        """
        dialog = QFileDialog(self)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setWindowTitle("Select Export Output Directory")
        
        # Default to current directory if available
        if self.current_directory:
            dialog.setDirectory(str(self.current_directory))
            
        if dialog.exec():
            selected_dirs = dialog.selectedFiles()
            if selected_dirs:
                return Path(selected_dirs[0])
                
        return None
        
    def perform_sample_export(self, sample_groups: List[SampleGroup], output_dir: Path):
        """
        Perform the actual sample export operation.
        
        Args:
            sample_groups: List of sample groups to export
            output_dir: Directory to save exported files
        """
        self.logger.info(f"Starting export of {len(sample_groups)} samples to {output_dir}")
        
        # Create FOV file mapping
        fov_file_map = {fov.index: fov.file_path for fov in self.discovered_fovs}
        
        exported_files = []
        export_errors = []
        
        for i, sample_group in enumerate(sample_groups):
            try:
                # Update progress
                progress_msg = f"Exporting sample {i+1}/{len(sample_groups)}: {sample_group.name}"
                self.status_bar.showMessage(progress_msg)
                self.logger.info(progress_msg)
                
                # Load FOV data for this sample
                self.merge_service.load_fov_data(sample_group, fov_file_map)
                
                # Export the sample
                output_file = self.merge_service.export_sample_csv(sample_group, output_dir)
                exported_files.append(output_file)
                
                self.logger.info(f"Successfully exported sample '{sample_group.name}' to {output_file}")
                
            except Exception as e:
                error_msg = f"Failed to export sample '{sample_group.name}': {str(e)}"
                self.logger.error(error_msg)
                export_errors.append(error_msg)
                
        # Show results
        self.show_export_results(exported_files, export_errors, output_dir)
        
    def show_export_results(self, exported_files: List[Path], errors: List[str], output_dir: Path):
        """
        Show export results to the user.
        
        Args:
            exported_files: List of successfully exported file paths
            errors: List of error messages
            output_dir: Export output directory
        """
        if exported_files and not errors:
            # Complete success
            success_msg = (
                f"Successfully exported {len(exported_files)} samples to:\n"
                f"{output_dir}\n\n"
                f"Exported files:\n" + 
                "\n".join([f"• {file.name}" for file in exported_files])
            )
            self.show_info("Export Complete", success_msg)
            self.status_bar.showMessage(f"Export complete: {len(exported_files)} samples exported")
            
        elif exported_files and errors:
            # Partial success
            warning_msg = (
                f"Export completed with some errors.\n\n"
                f"Successfully exported {len(exported_files)} samples:\n" +
                "\n".join([f"• {file.name}" for file in exported_files]) +
                f"\n\nErrors ({len(errors)}):\n" +
                "\n".join([f"• {error}" for error in errors])
            )
            self.show_warning("Export Completed with Errors", warning_msg)
            self.status_bar.showMessage(f"Export completed: {len(exported_files)} successful, {len(errors)} errors")
            
        else:
            # Complete failure
            error_msg = (
                f"Export failed for all samples.\n\n"
                f"Errors ({len(errors)}):\n" +
                "\n".join([f"• {error}" for error in errors])
            )
            self.show_error("Export Failed", error_msg)
            self.status_bar.showMessage("Export failed - see error details")
    
    def update_configuration_menu_state(self):
        """Update the configuration menu items enabled state."""
        # Enable save configuration if we have samples defined
        sample_groups = self.sample_table.get_sample_groups()
        has_samples = bool(sample_groups)
        self.save_config_action.setEnabled(has_samples)
    
    @Slot()
    def save_configuration(self):
        """Save current sample grouping configuration to JSON file."""
        try:
            # Get current sample groups
            sample_groups = self.sample_table.get_sample_groups()
            
            if not sample_groups:
                self.show_warning("Save Configuration", "No sample groups defined to save.")
                return
            
            # Select save location
            dialog = QFileDialog(self)
            dialog.setFileMode(QFileDialog.FileMode.AnyFile)
            dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
            dialog.setNameFilter("Configuration Files (*.json);;All Files (*)")
            dialog.setDefaultSuffix("json")
            dialog.setWindowTitle("Save Configuration")
            
            # Set default filename based on current directory
            if self.current_directory:
                default_name = f"{self.current_directory.name}_merge_config.json"
                dialog.selectFile(default_name)
                dialog.setDirectory(str(self.current_directory))
            
            if dialog.exec():
                selected_files = dialog.selectedFiles()
                if selected_files:
                    config_path = Path(selected_files[0])
                    
                    # Save configuration
                    self.merge_service.save_configuration(
                        sample_groups=sample_groups,
                        config_path=config_path,
                        processing_directory=self.current_directory
                    )
                    
                    # Show success message
                    self.show_info(
                        "Configuration Saved",
                        f"Sample grouping configuration saved to:\n{config_path}"
                    )
                    
                    self.logger.info(f"Configuration saved with {len(sample_groups)} samples")
                    
        except Exception as e:
            self.logger.error(f"Failed to save configuration: {e}")
            self.show_error("Save Configuration Failed", f"Failed to save configuration:\n\n{str(e)}")
    
    @Slot()
    def load_configuration(self):
        """Load sample grouping configuration from JSON file."""
        try:
            # Select configuration file
            dialog = QFileDialog(self)
            dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
            dialog.setNameFilter("Configuration Files (*.json);;All Files (*)")
            dialog.setWindowTitle("Load Configuration")
            
            # Set initial directory
            if self.current_directory:
                dialog.setDirectory(str(self.current_directory))
            
            if dialog.exec():
                selected_files = dialog.selectedFiles()
                if selected_files:
                    config_path = Path(selected_files[0])
                    
                    # Load configuration
                    config, load_warnings = self.merge_service.load_configuration(config_path)
                    
                    # Show load warnings if any
                    if load_warnings:
                        warning_msg = "Configuration loaded with warnings:\n\n" + "\n".join(load_warnings)
                        self.show_warning("Configuration Warnings", warning_msg)
                    
                    # Apply configuration
                    self.apply_loaded_configuration(config)
                    
                    self.logger.info(f"Configuration loaded from {config_path}")
                    
        except FileNotFoundError:
            self.show_error("Load Configuration Failed", "Configuration file not found.")
        except ValueError as e:
            self.show_error("Load Configuration Failed", f"Invalid configuration format:\n\n{str(e)}")
        except Exception as e:
            self.logger.error(f"Failed to load configuration: {e}")
            self.show_error("Load Configuration Failed", f"Failed to load configuration:\n\n{str(e)}")
    
    def apply_loaded_configuration(self, config: MergeConfiguration):
        """
        Apply loaded configuration to the current interface.
        
        Args:
            config: Loaded configuration object
        """
        # Check if we need to load a different processing directory
        if config.processing_directory and self.current_directory:
            config_dir = Path(config.processing_directory)
            if config_dir != self.current_directory:
                # Ask user if they want to switch directories
                reply = QMessageBox.question(
                    self,
                    "Different Processing Directory",
                    f"Configuration was created for directory:\n{config_dir}\n\n"
                    f"Current directory is:\n{self.current_directory}\n\n"
                    f"Do you want to switch to the configuration directory?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply == QMessageBox.StandardButton.Yes:
                    if config_dir.exists():
                        self.directory_selected.emit(config_dir)
                        # Wait for directory loading to complete before applying samples
                        QTimer.singleShot(500, lambda: self.apply_configuration_samples(config))
                        return
                    else:
                        self.show_warning(
                            "Directory Not Found",
                            f"Configuration directory not found:\n{config_dir}\n\n"
                            f"Applying configuration to current directory."
                        )
        
        # Apply samples to current directory
        self.apply_configuration_samples(config)
    
    def apply_configuration_samples(self, config: MergeConfiguration):
        """
        Apply sample groups from configuration to current interface.
        
        Args:
            config: Configuration with sample groups to apply
        """
        try:
            # Get available FOVs
            if not self.discovered_fovs:
                self.show_warning(
                    "No FOVs Available",
                    "No FOV data is currently loaded. Please select a processing directory first."
                )
                return
            
            available_fov_indices = [fov.index for fov in self.discovered_fovs]
            
            # Validate configuration compatibility
            validated_samples, validation_warnings = self.merge_service.validate_configuration_compatibility(
                config=config,
                available_fovs=available_fov_indices,
                processing_directory=self.current_directory
            )
            
            # Show validation warnings if any
            if validation_warnings:
                warning_msg = "Configuration applied with warnings:\n\n" + "\n".join(validation_warnings)
                self.show_warning("Configuration Compatibility", warning_msg)
            
            # Apply validated samples to the sample table
            if validated_samples:
                self.sample_table.load_sample_groups(validated_samples)
                
                success_msg = f"Loaded {len(validated_samples)} sample groups from configuration."
                if validation_warnings:
                    success_msg += f"\n\n{len(validation_warnings)} warnings were reported."
                
                self.show_info("Configuration Applied", success_msg)
                
                self.logger.info(f"Applied configuration: {len(validated_samples)} samples loaded")
            else:
                self.show_warning(
                    "No Valid Samples",
                    "No valid sample groups could be loaded from the configuration."
                )
            
            # Update merge service settings
            if hasattr(config, 'frames_per_hour'):
                self.merge_service.frames_per_hour = config.frames_per_hour
            
        except Exception as e:
            self.logger.error(f"Failed to apply configuration samples: {e}")
            self.show_error("Configuration Application Failed", f"Failed to apply configuration:\n\n{str(e)}")

    def closeEvent(self, event):
        """Handle application close event."""
        self.logger.info("Main window closing")
        
        # Clean up any running threads
        if self.discovery_thread and self.discovery_thread.isRunning():
            self.discovery_thread.quit()
            self.discovery_thread.wait()
            
        event.accept()
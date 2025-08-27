"""
Sample grouping table widget for PyAMA merge application.

This module provides an editable table widget for defining sample groups
with FOV range notation, real-time validation, and add/remove functionality.
"""

import logging
from typing import List, Optional, Dict, Tuple, Callable
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QVBoxLayout, QHBoxLayout, QWidget, QPushButton, QMessageBox
)
from PySide6.QtCore import Qt, Signal

from pyama_qt.merge.services.merge import SampleGroup
from pyama_qt.merge.utils.fov_parser import validate_fov_ranges, parse_fov_ranges, check_fov_conflicts

logger = logging.getLogger(__name__)


class SampleTable(QWidget):
    """
    Editable table widget for defining sample groups with FOV range notation.
    
    Features:
    - Two-column editable table: Name, FOVs
    - Real-time validation of FOV ranges
    - Add/remove sample rows
    - Selection handling for statistics display
    - Conflict detection between samples
    """
    
    # Signals
    sample_selection_changed = Signal(object)  # Emits selected SampleGroup or None
    samples_changed = Signal()  # Emits when sample data changes
    
    def __init__(self, parent=None):
        """
        Initialize the sample table widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.available_fovs = []  # List of available FOV indices
        self.validation_callback = None  # Optional callback for additional validation
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        
        # Create table
        self.table = QTableWidget()
        self._setup_table()
        layout.addWidget(self.table)
        
        # Create button layout
        button_layout = QHBoxLayout()
        
        self.add_button = QPushButton("Add Sample")
        self.remove_button = QPushButton("Remove Sample")
        self.remove_button.setEnabled(False)  # Disabled until selection
        
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addStretch()  # Push buttons to the left
        
        layout.addLayout(button_layout)
        
    def _setup_table(self):
        """Set up the table structure and appearance."""
        # Set up columns
        self.table.setColumnCount(2)
        self.table.setHorizontalHeaderLabels(["Name", "FOVs"])
        
        # Set selection behavior
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Configure header
        header = self.table.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        # Configure vertical header
        self.table.verticalHeader().setVisible(False)
        
        # Set alternating row colors for better readability
        self.table.setAlternatingRowColors(True)
        
        # Set minimum size
        self.table.setMinimumHeight(200)
        
        # Start with one empty row
        self._add_empty_row()
        
    def _connect_signals(self):
        """Connect widget signals."""
        self.add_button.clicked.connect(self._add_sample_row)
        self.remove_button.clicked.connect(self._remove_selected_row)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        
    def set_available_fovs(self, fov_indices: List[int]):
        """
        Set the list of available FOV indices for validation.
        
        Args:
            fov_indices: List of available FOV indices (0-based)
        """
        self.available_fovs = sorted(fov_indices)
        logger.debug(f"Set available FOVs: {self.available_fovs}")
        
        # Re-validate all existing entries
        self._validate_all_rows()
        
    def set_validation_callback(self, callback: Callable[[List[Tuple[str, str]]], List[str]]):
        """
        Set an optional callback for additional validation (e.g., conflict checking).
        
        Args:
            callback: Function that takes list of (name, fov_ranges) tuples and returns error messages
        """
        self.validation_callback = callback
        
    def _add_empty_row(self):
        """Add an empty row to the table."""
        row_count = self.table.rowCount()
        self.table.insertRow(row_count)
        
        # Create editable items
        name_item = QTableWidgetItem("")
        fov_item = QTableWidgetItem("")
        
        self.table.setItem(row_count, 0, name_item)
        self.table.setItem(row_count, 1, fov_item)
        
        logger.debug(f"Added empty row at index {row_count}")
        
    def _add_sample_row(self):
        """Add a new sample row."""
        self._add_empty_row()
        
        # Select the new row
        new_row = self.table.rowCount() - 1
        self.table.selectRow(new_row)
        
        # Focus on the name cell for immediate editing
        name_item = self.table.item(new_row, 0)
        if name_item:
            self.table.setCurrentItem(name_item)
            self.table.editItem(name_item)
            
    def _remove_selected_row(self):
        """Remove the currently selected row."""
        current_row = self.table.currentRow()
        if current_row < 0:
            return
            
        # Confirm deletion if the row has data
        name_item = self.table.item(current_row, 0)
        fov_item = self.table.item(current_row, 1)
        
        has_data = (name_item and name_item.text().strip()) or (fov_item and fov_item.text().strip())
        
        if has_data:
            reply = QMessageBox.question(
                self, 
                "Confirm Deletion",
                "Are you sure you want to remove this sample?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.table.removeRow(current_row)
        logger.debug(f"Removed row {current_row}")
        
        # Ensure we always have at least one row
        if self.table.rowCount() == 0:
            self._add_empty_row()
            
        # Emit changes signal
        self.samples_changed.emit()
        
    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle item changes for real-time validation."""
        row = item.row()
        col = item.column()
        
        logger.debug(f"Item changed at row {row}, col {col}: '{item.text()}'")
        
        # Validate the row
        self._validate_row(row)
        
        # If this is the last row and it has content, add a new empty row
        if row == self.table.rowCount() - 1 and self._row_has_content(row):
            self._add_empty_row()
            
        # Emit changes signal
        self.samples_changed.emit()
        
    def _on_selection_changed(self):
        """Handle selection changes."""
        current_row = self.table.currentRow()
        self.remove_button.setEnabled(current_row >= 0)
        
        # Get selected sample group
        selected_sample = self._get_sample_group_from_row(current_row) if current_row >= 0 else None
        
        # Emit selection changed signal
        self.sample_selection_changed.emit(selected_sample)
        
    def _row_has_content(self, row: int) -> bool:
        """Check if a row has any content."""
        name_item = self.table.item(row, 0)
        fov_item = self.table.item(row, 1)
        
        name_text = name_item.text().strip() if name_item else ""
        fov_text = fov_item.text().strip() if fov_item else ""
        
        return bool(name_text or fov_text)
        
    def _validate_row(self, row: int):
        """Validate a single row and update its appearance."""
        name_item = self.table.item(row, 0)
        fov_item = self.table.item(row, 1)
        
        if not name_item or not fov_item:
            return
            
        name_text = name_item.text().strip()
        fov_text = fov_item.text().strip()
        
        # Reset background colors
        name_item.setBackground(Qt.GlobalColor.white)
        fov_item.setBackground(Qt.GlobalColor.white)
        
        # Clear tooltips
        name_item.setToolTip("")
        fov_item.setToolTip("")
        
        # Skip validation for empty rows
        if not name_text and not fov_text:
            return
            
        errors = []
        
        # Validate name
        if not name_text:
            errors.append("Sample name is required")
            name_item.setBackground(Qt.GlobalColor.yellow)
            name_item.setToolTip("Sample name is required")
        
        # Validate FOV ranges
        if fov_text:
            is_valid, fov_errors = validate_fov_ranges(fov_text, self.available_fovs)
            if not is_valid:
                errors.extend(fov_errors)
                fov_item.setBackground(Qt.GlobalColor.red)
                fov_item.setToolTip("; ".join(fov_errors))
        elif name_text:  # Name exists but no FOVs
            errors.append("FOV ranges are required")
            fov_item.setBackground(Qt.GlobalColor.yellow)
            fov_item.setToolTip("FOV ranges are required")
            
        # Additional validation via callback
        if self.validation_callback and name_text and fov_text:
            all_samples = self._get_all_sample_data()
            additional_errors = self.validation_callback(all_samples)
            
            # Check if any errors relate to this sample
            for error in additional_errors:
                if name_text in error:
                    errors.append(error)
                    name_item.setBackground(Qt.GlobalColor.red)
                    fov_item.setBackground(Qt.GlobalColor.red)
                    
                    # Update tooltips
                    current_tooltip = name_item.toolTip()
                    new_tooltip = f"{current_tooltip}; {error}" if current_tooltip else error
                    name_item.setToolTip(new_tooltip)
                    fov_item.setToolTip(new_tooltip)
        
        if errors:
            logger.debug(f"Validation errors for row {row}: {errors}")
        
    def _validate_all_rows(self):
        """Validate all rows in the table."""
        for row in range(self.table.rowCount()):
            self._validate_row(row)
            
    def _get_sample_group_from_row(self, row: int) -> Optional[SampleGroup]:
        """
        Create a SampleGroup from a table row.
        
        Args:
            row: Row index
            
        Returns:
            SampleGroup if row has valid data, None otherwise
        """
        if row < 0 or row >= self.table.rowCount():
            return None
            
        name_item = self.table.item(row, 0)
        fov_item = self.table.item(row, 1)
        
        if not name_item or not fov_item:
            return None
            
        name_text = name_item.text().strip()
        fov_text = fov_item.text().strip()
        
        if not name_text or not fov_text:
            return None
            
        try:
            # Parse FOV ranges
            resolved_fovs = parse_fov_ranges(fov_text)
            
            # Create sample group
            sample_group = SampleGroup(
                name=name_text,
                fov_ranges=fov_text,
                resolved_fovs=resolved_fovs
            )
            
            return sample_group
            
        except ValueError as e:
            logger.debug(f"Failed to create sample group from row {row}: {e}")
            return None
            
    def _get_all_sample_data(self) -> List[Tuple[str, str]]:
        """
        Get all sample data as (name, fov_ranges) tuples.
        
        Returns:
            List of (name, fov_ranges) tuples for all rows with content
        """
        samples = []
        
        for row in range(self.table.rowCount()):
            name_item = self.table.item(row, 0)
            fov_item = self.table.item(row, 1)
            
            if not name_item or not fov_item:
                continue
                
            name_text = name_item.text().strip()
            fov_text = fov_item.text().strip()
            
            if name_text and fov_text:
                samples.append((name_text, fov_text))
                
        return samples
        
    def get_sample_groups(self) -> List[SampleGroup]:
        """
        Get all valid sample groups from the table.
        
        Returns:
            List of SampleGroup objects
        """
        sample_groups = []
        
        for row in range(self.table.rowCount()):
            sample_group = self._get_sample_group_from_row(row)
            if sample_group:
                sample_groups.append(sample_group)
                
        logger.debug(f"Retrieved {len(sample_groups)} sample groups from table")
        return sample_groups
        
    def set_sample_groups(self, sample_groups: List[SampleGroup]):
        """
        Populate the table with sample groups.
        
        Args:
            sample_groups: List of SampleGroup objects to display
        """
        logger.debug(f"Setting {len(sample_groups)} sample groups in table")
        
        # Clear existing data
        self.table.setRowCount(0)
        
        # Add sample groups
        for sample_group in sample_groups:
            row = self.table.rowCount()
            self.table.insertRow(row)
            
            name_item = QTableWidgetItem(sample_group.name)
            fov_item = QTableWidgetItem(sample_group.fov_ranges)
            
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, fov_item)
            
        # Add empty row for new entries
        self._add_empty_row()
        
        # Validate all rows
        self._validate_all_rows()
        
        logger.info(f"Sample table populated with {len(sample_groups)} sample groups")
        
    def load_sample_groups(self, sample_groups: List[SampleGroup]):
        """
        Load sample groups from configuration, with validation and user feedback.
        
        This method is similar to set_sample_groups but provides additional
        validation and is specifically designed for loading from saved configurations.
        
        Args:
            sample_groups: List of SampleGroup objects to load
        """
        logger.info(f"Loading {len(sample_groups)} sample groups from configuration")
        
        # Use the existing set_sample_groups method
        self.set_sample_groups(sample_groups)
        
        # Emit signals to update dependent widgets
        self.samples_changed.emit()
        
        # If there's a selection, emit selection changed
        if self.table.rowCount() > 0:
            self.table.selectRow(0)  # Select first row by default
        
    def clear_table(self):
        """Clear all data from the table."""
        self.table.setRowCount(0)
        self._add_empty_row()
        logger.debug("Sample table cleared")
        
    def get_selected_sample_group(self) -> Optional[SampleGroup]:
        """
        Get the currently selected sample group.
        
        Returns:
            SampleGroup if a valid row is selected, None otherwise
        """
        current_row = self.table.currentRow()
        return self._get_sample_group_from_row(current_row)
        
    def validate_all_samples(self) -> List[str]:
        """
        Validate all samples and return error messages.
        
        Returns:
            List of validation error messages
        """
        errors = []
        sample_data = self._get_all_sample_data()
        
        if not sample_data:
            return ["No samples defined"]
            
        # Check for duplicate names
        names = [name for name, _ in sample_data]
        duplicate_names = set([name for name in names if names.count(name) > 1])
        if duplicate_names:
            errors.append(f"Duplicate sample names: {sorted(duplicate_names)}")
            
        # Check FOV conflicts
        fov_conflicts = check_fov_conflicts(sample_data, self.available_fovs)
        errors.extend(fov_conflicts)
        
        # Individual sample validation
        for name, fov_ranges in sample_data:
            is_valid, sample_errors = validate_fov_ranges(fov_ranges, self.available_fovs)
            if not is_valid:
                errors.extend([f"Sample '{name}': {error}" for error in sample_errors])
                
        return errors
        
    def get_sample_statistics(self) -> Dict[str, any]:
        """
        Get statistics about the current sample configuration.
        
        Returns:
            Dictionary with sample statistics
        """
        sample_groups = self.get_sample_groups()
        
        total_fovs = sum(len(sg.resolved_fovs) for sg in sample_groups)
        all_assigned_fovs = set()
        for sg in sample_groups:
            all_assigned_fovs.update(sg.resolved_fovs)
            
        stats = {
            'sample_count': len(sample_groups),
            'total_assigned_fovs': total_fovs,
            'unique_assigned_fovs': len(all_assigned_fovs),
            'available_fovs': len(self.available_fovs),
            'unassigned_fovs': len(set(self.available_fovs) - all_assigned_fovs),
            'samples': []
        }
        
        for sg in sample_groups:
            sample_stats = {
                'name': sg.name,
                'fov_count': len(sg.resolved_fovs),
                'fov_indices': sg.resolved_fovs,
                'fov_ranges': sg.fov_ranges
            }
            stats['samples'].append(sample_stats)
            
        return stats
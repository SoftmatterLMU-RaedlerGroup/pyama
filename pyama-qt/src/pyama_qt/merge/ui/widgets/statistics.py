"""
Statistics display widget for PyAMA merge application.

This module provides a widget that displays detailed statistics for selected
sample groups, including resolved FOV indices, counts, cell totals, and error
information for invalid FOV ranges.
"""

import logging
from typing import Optional, List, Dict
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit, QFrame
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from pyama_qt.merge.services.merge import SampleGroup
from pyama_qt.merge.services.discovery import FOVInfo
from pyama_qt.merge.utils.fov_parser import get_fov_range_summary

logger = logging.getLogger(__name__)


class StatisticsWidget(QWidget):
    """
    Widget for displaying detailed sample statistics and validation information.
    
    Features:
    - Shows resolved FOV indices, FOV count, and cell totals
    - Displays error information for invalid FOV ranges
    - Updates when sample selection changes
    - Shows instructions when no sample is selected
    """
    
    def __init__(self, parent=None):
        """
        Initialize the statistics widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self.available_fovs = []  # List of available FOV indices
        self.fov_info_map = {}   # Map of FOV index to FOVInfo
        self.current_sample = None  # Currently selected sample
        
        self._setup_ui()
        self._show_no_selection_message()
        
    def _setup_ui(self):
        """Set up the user interface."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # Title
        title_label = QLabel("Sample Statistics")
        title_font = QFont()
        title_font.setBold(True)
        title_font.setPointSize(12)
        title_label.setFont(title_font)
        layout.addWidget(title_label)
        
        # Separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)
        
        # Content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(8)
        layout.addWidget(self.content_widget)
        
        # Set minimum size
        self.setMinimumHeight(200)
        self.setMaximumHeight(400)
        
    def _clear_content(self):
        """Clear all content from the widget."""
        # Remove all widgets from content layout
        while self.content_layout.count():
            child = self.content_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
                
    def _show_no_selection_message(self):
        """Show instructions when no sample is selected."""
        self._clear_content()
        
        message_label = QLabel("Select a sample from the table above to view detailed statistics.")
        message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        message_label.setStyleSheet("color: #666; font-style: italic; padding: 20px;")
        message_label.setWordWrap(True)
        
        self.content_layout.addWidget(message_label)
        self.content_layout.addStretch()
        
    def _create_info_row(self, label: str, value: str, is_error: bool = False) -> QWidget:
        """
        Create a row with label and value.
        
        Args:
            label: Label text
            value: Value text
            is_error: Whether this is an error message
            
        Returns:
            Widget containing the row
        """
        row_widget = QWidget()
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(10)
        
        # Label
        label_widget = QLabel(f"{label}:")
        label_widget.setMinimumWidth(120)
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        row_layout.addWidget(label_widget)
        
        # Value
        value_widget = QLabel(value)
        value_widget.setWordWrap(True)
        
        if is_error:
            value_widget.setStyleSheet("color: #d32f2f; font-weight: bold;")
        else:
            value_widget.setStyleSheet("color: #333;")
            
        row_layout.addWidget(value_widget, 1)
        
        return row_widget
        
    def _create_multiline_info(self, label: str, content: str, is_error: bool = False) -> QWidget:
        """
        Create a multiline information display.
        
        Args:
            label: Label text
            content: Content text
            is_error: Whether this is an error message
            
        Returns:
            Widget containing the multiline info
        """
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        
        # Label
        label_widget = QLabel(f"{label}:")
        label_font = QFont()
        label_font.setBold(True)
        label_widget.setFont(label_font)
        layout.addWidget(label_widget)
        
        # Content
        content_widget = QTextEdit()
        content_widget.setPlainText(content)
        content_widget.setReadOnly(True)
        content_widget.setMaximumHeight(80)
        content_widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        if is_error:
            content_widget.setStyleSheet("""
                QTextEdit {
                    background-color: #ffebee;
                    border: 1px solid #d32f2f;
                    color: #d32f2f;
                    font-weight: bold;
                }
            """)
        else:
            content_widget.setStyleSheet("""
                QTextEdit {
                    background-color: #f5f5f5;
                    border: 1px solid #ddd;
                    color: #333;
                }
            """)
            
        layout.addWidget(content_widget)
        
        return container
        
    def set_available_fovs(self, fov_infos: List[FOVInfo]):
        """
        Set the list of available FOVs with their information.
        
        Args:
            fov_infos: List of FOVInfo objects
        """
        self.available_fovs = [fov.index for fov in fov_infos]
        self.fov_info_map = {fov.index: fov for fov in fov_infos}
        
        logger.debug(f"Set available FOVs: {self.available_fovs}")
        
        # Update display if we have a current sample
        if self.current_sample:
            self.update_sample_statistics(self.current_sample)
            
    def update_sample_statistics(self, sample_group: Optional[SampleGroup]):
        """
        Update the statistics display for the selected sample group.
        
        Args:
            sample_group: Selected sample group, or None if no selection
        """
        self.current_sample = sample_group
        
        if sample_group is None:
            self._show_no_selection_message()
            return
            
        logger.debug(f"Updating statistics for sample: {sample_group.name}")
        
        self._clear_content()
        
        # Get FOV range summary for validation
        range_summary = get_fov_range_summary(sample_group.fov_ranges, self.available_fovs)
        
        # Sample name
        name_row = self._create_info_row("Sample Name", sample_group.name)
        self.content_layout.addWidget(name_row)
        
        # FOV ranges (input)
        ranges_row = self._create_info_row("FOV Ranges", sample_group.fov_ranges)
        self.content_layout.addWidget(ranges_row)
        
        # Check if there are validation errors
        if not range_summary['valid']:
            # Show errors
            error_text = "\n".join(range_summary['errors'])
            error_widget = self._create_multiline_info("Validation Errors", error_text, is_error=True)
            self.content_layout.addWidget(error_widget)
            
            # Show partial results if any FOVs were resolved
            if range_summary['resolved_fovs']:
                resolved_text = ", ".join(map(str, sorted(range_summary['resolved_fovs'])))
                resolved_row = self._create_info_row("Partially Resolved FOVs", resolved_text)
                self.content_layout.addWidget(resolved_row)
                
                count_row = self._create_info_row("Partial FOV Count", str(len(range_summary['resolved_fovs'])))
                self.content_layout.addWidget(count_row)
        else:
            # Show valid statistics
            resolved_fovs = range_summary['resolved_fovs']
            
            # Resolved FOV indices
            if resolved_fovs:
                resolved_text = ", ".join(map(str, sorted(resolved_fovs)))
                if len(resolved_text) > 100:  # If too long, use multiline display
                    resolved_widget = self._create_multiline_info("Resolved FOV Indices", resolved_text)
                    self.content_layout.addWidget(resolved_widget)
                else:
                    resolved_row = self._create_info_row("Resolved FOV Indices", resolved_text)
                    self.content_layout.addWidget(resolved_row)
                
                # FOV count
                count_row = self._create_info_row("FOV Count", str(len(resolved_fovs)))
                self.content_layout.addWidget(count_row)
                
                # Calculate total cell count from available FOV info
                total_cells = 0
                missing_cell_info = []
                
                for fov_idx in resolved_fovs:
                    if fov_idx in self.fov_info_map:
                        total_cells += self.fov_info_map[fov_idx].cell_count
                    else:
                        missing_cell_info.append(fov_idx)
                
                if missing_cell_info:
                    cell_text = f"{total_cells} (missing info for FOVs: {missing_cell_info})"
                    cell_row = self._create_info_row("Total Cell Count", cell_text, is_error=True)
                else:
                    cell_row = self._create_info_row("Total Cell Count", str(total_cells))
                self.content_layout.addWidget(cell_row)
                
                # Show individual FOV details if not too many
                if len(resolved_fovs) <= 10:
                    fov_details = []
                    for fov_idx in sorted(resolved_fovs):
                        if fov_idx in self.fov_info_map:
                            fov_info = self.fov_info_map[fov_idx]
                            fov_details.append(f"FOV {fov_idx}: {fov_info.cell_count} cells")
                        else:
                            fov_details.append(f"FOV {fov_idx}: cell count unknown")
                    
                    details_text = "\n".join(fov_details)
                    details_widget = self._create_multiline_info("FOV Details", details_text)
                    self.content_layout.addWidget(details_widget)
                    
            else:
                # No FOVs resolved
                no_fovs_row = self._create_info_row("Status", "No FOVs assigned", is_error=True)
                self.content_layout.addWidget(no_fovs_row)
        
        # Add stretch to push content to top
        self.content_layout.addStretch()
        
        logger.debug(f"Statistics updated for sample '{sample_group.name}': "
                    f"{len(range_summary['resolved_fovs'])} FOVs, valid={range_summary['valid']}")
        
    def clear_statistics(self):
        """Clear the statistics display."""
        self.current_sample = None
        self._show_no_selection_message()
        logger.debug("Statistics display cleared")
        
    def get_current_sample_summary(self) -> Optional[Dict[str, any]]:
        """
        Get a summary of the currently displayed sample statistics.
        
        Returns:
            Dictionary with sample summary or None if no sample selected
        """
        if not self.current_sample:
            return None
            
        range_summary = get_fov_range_summary(self.current_sample.fov_ranges, self.available_fovs)
        
        # Calculate total cells
        total_cells = 0
        for fov_idx in range_summary['resolved_fovs']:
            if fov_idx in self.fov_info_map:
                total_cells += self.fov_info_map[fov_idx].cell_count
        
        return {
            'name': self.current_sample.name,
            'fov_ranges': self.current_sample.fov_ranges,
            'resolved_fovs': range_summary['resolved_fovs'],
            'fov_count': len(range_summary['resolved_fovs']),
            'total_cells': total_cells,
            'is_valid': range_summary['valid'],
            'errors': range_summary['errors']
        }
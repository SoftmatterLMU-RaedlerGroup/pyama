"""
FOV information table widget for PyAMA merge application.

This module provides a read-only table widget that displays FOV index and cell count
information for discovered FOV trace files.
"""

import logging
from typing import List, Optional
from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView
)
from PySide6.QtCore import Qt

from pyama_qt.merge.services.discovery import FOVInfo

logger = logging.getLogger(__name__)


class FOVTable(QTableWidget):
    """
    Read-only table widget displaying FOV information.
    
    Shows FOV index and cell count for each discovered FOV trace file.
    The table is read-only and automatically sized to fit content.
    """
    
    def __init__(self, parent=None):
        """
        Initialize the FOV table widget.
        
        Args:
            parent: Parent widget
        """
        super().__init__(parent)
        self._setup_table()
        
    def _setup_table(self):
        """Set up the table structure and appearance."""
        # Set up columns
        self.setColumnCount(2)
        self.setHorizontalHeaderLabels(["FOV Index", "Cell Count"])
        
        # Make table read-only
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        
        # Set selection behavior
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # Configure header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        
        # Configure vertical header
        self.verticalHeader().setVisible(False)
        
        # Set alternating row colors for better readability
        self.setAlternatingRowColors(True)
        
        # Set minimum size
        self.setMinimumHeight(150)
        
    def populate_from_fov_list(self, fov_infos: List[FOVInfo]):
        """
        Populate the table with FOV information.
        
        Args:
            fov_infos: List of FOVInfo objects to display
        """
        logger.debug(f"Populating FOV table with {len(fov_infos)} FOVs")
        
        # Clear existing data
        self.clear_table()
        
        if not fov_infos:
            logger.info("No FOV data to display")
            return
            
        # Set row count
        self.setRowCount(len(fov_infos))
        
        # Populate rows
        for row, fov_info in enumerate(fov_infos):
            self._add_fov_row(row, fov_info)
            
        # Resize columns to content
        self.resizeColumnsToContents()
        
        logger.info(f"FOV table populated with {len(fov_infos)} entries")
        
    def _add_fov_row(self, row: int, fov_info: FOVInfo):
        """
        Add a single FOV row to the table.
        
        Args:
            row: Row index to add
            fov_info: FOVInfo object containing the data
        """
        # FOV Index column
        index_item = QTableWidgetItem(str(fov_info.index))
        index_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        index_item.setData(Qt.ItemDataRole.UserRole, fov_info)  # Store FOVInfo for later use
        self.setItem(row, 0, index_item)
        
        # Cell Count column
        count_item = QTableWidgetItem(str(fov_info.cell_count))
        count_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setItem(row, 1, count_item)
        
    def clear_table(self):
        """Clear all data from the table."""
        self.setRowCount(0)
        self.setHorizontalHeaderLabels(["FOV Index", "Cell Count"])
        
    def get_selected_fov_info(self) -> Optional[FOVInfo]:
        """
        Get the FOVInfo object for the currently selected row.
        
        Returns:
            FOVInfo object if a row is selected, None otherwise
        """
        current_row = self.currentRow()
        if current_row < 0:
            return None
            
        index_item = self.item(current_row, 0)
        if index_item is None:
            return None
            
        return index_item.data(Qt.ItemDataRole.UserRole)
        
    def get_all_fov_infos(self) -> List[FOVInfo]:
        """
        Get all FOVInfo objects currently displayed in the table.
        
        Returns:
            List of FOVInfo objects
        """
        fov_infos = []
        for row in range(self.rowCount()):
            index_item = self.item(row, 0)
            if index_item is not None:
                fov_info = index_item.data(Qt.ItemDataRole.UserRole)
                if fov_info is not None:
                    fov_infos.append(fov_info)
        return fov_infos
        
    def get_total_cell_count(self) -> int:
        """
        Get the total number of cells across all FOVs.
        
        Returns:
            Total cell count
        """
        total = 0
        for row in range(self.rowCount()):
            count_item = self.item(row, 1)
            if count_item is not None:
                try:
                    total += int(count_item.text())
                except ValueError:
                    logger.warning(f"Invalid cell count in row {row}: {count_item.text()}")
        return total
        
    def get_fov_count(self) -> int:
        """
        Get the number of FOVs currently displayed.
        
        Returns:
            Number of FOVs
        """
        return self.rowCount()
"""
Tests for the SampleTable widget.
"""

import pytest
from unittest.mock import Mock, patch
from PySide6.QtWidgets import QApplication, QTableWidgetItem
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from pyama_qt.merge.ui.widgets.sample_table import SampleTable
from pyama_qt.merge.services.merge import SampleGroup


@pytest.fixture
def app():
    """Create QApplication instance for testing."""
    return QApplication.instance() or QApplication([])


@pytest.fixture
def sample_table(app):
    """Create SampleTable widget for testing."""
    table = SampleTable()
    table.set_available_fovs([0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
    return table


class TestSampleTable:
    """Test cases for SampleTable widget."""
    
    def test_initialization(self, sample_table):
        """Test widget initialization."""
        # Should have 2 columns
        assert sample_table.table.columnCount() == 2
        
        # Should have correct headers
        headers = []
        for i in range(sample_table.table.columnCount()):
            headers.append(sample_table.table.horizontalHeaderItem(i).text())
        assert headers == ["Name", "FOVs"]
        
        # Should start with one empty row
        assert sample_table.table.rowCount() == 1
        
        # Remove button should be disabled initially
        assert not sample_table.remove_button.isEnabled()
        
    def test_set_available_fovs(self, sample_table):
        """Test setting available FOVs."""
        fov_list = [0, 1, 2, 5, 8, 10]
        sample_table.set_available_fovs(fov_list)
        
        assert sample_table.available_fovs == sorted(fov_list)
        
    def test_add_sample_row(self, sample_table):
        """Test adding sample rows."""
        initial_rows = sample_table.table.rowCount()
        
        # Add a row
        sample_table._add_sample_row()
        
        # Should have one more row
        assert sample_table.table.rowCount() == initial_rows + 1
        
    def test_sample_data_entry(self, sample_table):
        """Test entering sample data."""
        # Enter sample data in first row
        name_item = sample_table.table.item(0, 0)
        fov_item = sample_table.table.item(0, 1)
        
        name_item.setText("Sample_1")
        fov_item.setText("0-2,5")
        
        # Trigger validation
        sample_table._validate_row(0)
        
        # Should be valid (white background)
        assert name_item.background().color() == Qt.GlobalColor.white
        assert fov_item.background().color() == Qt.GlobalColor.white
        
    def test_invalid_fov_ranges(self, sample_table):
        """Test validation of invalid FOV ranges."""
        # Enter invalid FOV range
        name_item = sample_table.table.item(0, 0)
        fov_item = sample_table.table.item(0, 1)
        
        name_item.setText("Sample_1")
        fov_item.setText("0-2,15")  # 15 is not available
        
        # Trigger validation
        sample_table._validate_row(0)
        
        # FOV item should have red background (error)
        assert fov_item.background().color() == Qt.GlobalColor.red
        assert "not available" in fov_item.toolTip()
        
    def test_empty_name_validation(self, sample_table):
        """Test validation when name is empty."""
        # Enter FOVs but no name
        name_item = sample_table.table.item(0, 0)
        fov_item = sample_table.table.item(0, 1)
        
        name_item.setText("")
        fov_item.setText("0-2")
        
        # Trigger validation
        sample_table._validate_row(0)
        
        # Name item should have yellow background (warning)
        assert name_item.background().color() == Qt.GlobalColor.yellow
        assert "required" in name_item.toolTip()
        
    def test_empty_fov_validation(self, sample_table):
        """Test validation when FOVs are empty."""
        # Enter name but no FOVs
        name_item = sample_table.table.item(0, 0)
        fov_item = sample_table.table.item(0, 1)
        
        name_item.setText("Sample_1")
        fov_item.setText("")
        
        # Trigger validation
        sample_table._validate_row(0)
        
        # FOV item should have yellow background (warning)
        assert fov_item.background().color() == Qt.GlobalColor.yellow
        assert "required" in fov_item.toolTip()
        
    def test_get_sample_groups(self, sample_table):
        """Test getting sample groups from table."""
        # Add sample data
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2,5")
        
        # Add another row with data
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_2")
        sample_table.table.item(1, 1).setText("3,4,6-8")
        
        # Get sample groups
        sample_groups = sample_table.get_sample_groups()
        
        assert len(sample_groups) == 2
        
        # Check first sample
        assert sample_groups[0].name == "Sample_1"
        assert sample_groups[0].fov_ranges == "0-2,5"
        assert sample_groups[0].resolved_fovs == [0, 1, 2, 5]
        
        # Check second sample
        assert sample_groups[1].name == "Sample_2"
        assert sample_groups[1].fov_ranges == "3,4,6-8"
        assert sample_groups[1].resolved_fovs == [3, 4, 6, 7, 8]
        
    def test_set_sample_groups(self, sample_table):
        """Test setting sample groups in table."""
        sample_groups = [
            SampleGroup(name="Sample_A", fov_ranges="0-1", resolved_fovs=[0, 1]),
            SampleGroup(name="Sample_B", fov_ranges="2,4-5", resolved_fovs=[2, 4, 5])
        ]
        
        sample_table.set_sample_groups(sample_groups)
        
        # Should have 3 rows (2 samples + 1 empty)
        assert sample_table.table.rowCount() == 3
        
        # Check first sample
        assert sample_table.table.item(0, 0).text() == "Sample_A"
        assert sample_table.table.item(0, 1).text() == "0-1"
        
        # Check second sample
        assert sample_table.table.item(1, 0).text() == "Sample_B"
        assert sample_table.table.item(1, 1).text() == "2,4-5"
        
        # Third row should be empty
        assert sample_table.table.item(2, 0).text() == ""
        assert sample_table.table.item(2, 1).text() == ""
        
    def test_validate_all_samples(self, sample_table):
        """Test validation of all samples."""
        # Add valid samples
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_2")
        sample_table.table.item(1, 1).setText("3-5")
        
        # Should be valid
        errors = sample_table.validate_all_samples()
        assert len(errors) == 0
        
    def test_validate_duplicate_names(self, sample_table):
        """Test validation with duplicate sample names."""
        # Add samples with duplicate names
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_1")  # Duplicate name
        sample_table.table.item(1, 1).setText("3-5")
        
        # Should have validation error
        errors = sample_table.validate_all_samples()
        assert len(errors) > 0
        assert any("Duplicate" in error for error in errors)
        
    def test_validate_fov_conflicts(self, sample_table):
        """Test validation with FOV conflicts."""
        # Add samples with overlapping FOVs
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-3")
        
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_2")
        sample_table.table.item(1, 1).setText("2-5")  # Overlaps with Sample_1
        
        # Should have validation error
        errors = sample_table.validate_all_samples()
        assert len(errors) > 0
        assert any("assigned to both" in error for error in errors)
        
    def test_get_sample_statistics(self, sample_table):
        """Test getting sample statistics."""
        # Add sample data
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_2")
        sample_table.table.item(1, 1).setText("5,7-8")
        
        # Get statistics
        stats = sample_table.get_sample_statistics()
        
        assert stats['sample_count'] == 2
        assert stats['total_assigned_fovs'] == 6  # 3 + 3 FOVs
        assert stats['unique_assigned_fovs'] == 6  # No overlaps
        assert stats['available_fovs'] == 10
        assert stats['unassigned_fovs'] == 4  # 10 - 6
        
        # Check individual sample stats
        assert len(stats['samples']) == 2
        assert stats['samples'][0]['name'] == "Sample_1"
        assert stats['samples'][0]['fov_count'] == 3
        assert stats['samples'][1]['name'] == "Sample_2"
        assert stats['samples'][1]['fov_count'] == 3
        
    def test_clear_table(self, sample_table):
        """Test clearing the table."""
        # Add some data
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        sample_table._add_sample_row()
        
        # Clear table
        sample_table.clear_table()
        
        # Should have only one empty row
        assert sample_table.table.rowCount() == 1
        assert sample_table.table.item(0, 0).text() == ""
        assert sample_table.table.item(0, 1).text() == ""
        
    def test_remove_row(self, sample_table):
        """Test removing a row."""
        # Add data to first row
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        
        # Add another row
        sample_table._add_sample_row()
        sample_table.table.item(1, 0).setText("Sample_2")
        sample_table.table.item(1, 1).setText("3-5")
        
        # Select first row
        sample_table.table.selectRow(0)
        
        # Mock the message box to always return Yes
        with patch('pyama_qt.merge.ui.widgets.sample_table.QMessageBox.question', return_value=2):  # Yes = 2
            sample_table._remove_selected_row()
        
        # Should have one less row
        assert sample_table.table.rowCount() == 2  # 1 remaining + 1 empty
        
        # First row should now be Sample_2
        assert sample_table.table.item(0, 0).text() == "Sample_2"
        
    def test_selection_signals(self, sample_table):
        """Test selection change signals."""
        # Mock signal handler
        signal_handler = Mock()
        sample_table.sample_selection_changed.connect(signal_handler)
        
        # Add sample data
        sample_table.table.item(0, 0).setText("Sample_1")
        sample_table.table.item(0, 1).setText("0-2")
        
        # Select the row
        sample_table.table.selectRow(0)
        sample_table._on_selection_changed()
        
        # Signal should have been emitted
        signal_handler.assert_called_once()
        
        # Get the emitted sample group
        emitted_sample = signal_handler.call_args[0][0]
        assert emitted_sample is not None
        assert emitted_sample.name == "Sample_1"
        
    def test_changes_signals(self, sample_table):
        """Test changes signals."""
        # Mock signal handler
        signal_handler = Mock()
        sample_table.samples_changed.connect(signal_handler)
        
        # Change item text
        item = sample_table.table.item(0, 0)
        item.setText("Sample_1")
        sample_table._on_item_changed(item)
        
        # Signal should have been emitted
        signal_handler.assert_called_once()
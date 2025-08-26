"""
Tests for FOV table widget.
"""

import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from pyama_qt.merge.ui.widgets.fov_table import FOVTable
from pyama_qt.merge.services.discovery import FOVInfo


@pytest.fixture
def app():
    """Create QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def sample_fov_infos():
    """Create sample FOVInfo objects for testing."""
    return [
        FOVInfo(
            index=0,
            cell_count=45,
            file_path=Path("test_fov0000_traces.csv"),
            has_quality_data=True,
            frame_count=120
        ),
        FOVInfo(
            index=1,
            cell_count=52,
            file_path=Path("test_fov0001_traces.csv"),
            has_quality_data=False,
            frame_count=120
        ),
        FOVInfo(
            index=2,
            cell_count=38,
            file_path=Path("test_fov0002_traces.csv"),
            has_quality_data=True,
            frame_count=120
        )
    ]


def test_fov_table_initialization(app):
    """Test FOV table initialization."""
    table = FOVTable()
    
    # Check basic setup
    assert table.columnCount() == 2
    assert table.rowCount() == 0
    assert table.horizontalHeaderItem(0).text() == "FOV Index"
    assert table.horizontalHeaderItem(1).text() == "Cell Count"
    
    # Check read-only behavior
    assert not table.editTriggers()


def test_populate_from_fov_list(app, sample_fov_infos):
    """Test populating table with FOV data."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    # Check row count
    assert table.rowCount() == 3
    
    # Check data in first row
    assert table.item(0, 0).text() == "0"
    assert table.item(0, 1).text() == "45"
    
    # Check data in second row
    assert table.item(1, 0).text() == "1"
    assert table.item(1, 1).text() == "52"
    
    # Check data in third row
    assert table.item(2, 0).text() == "2"
    assert table.item(2, 1).text() == "38"


def test_populate_empty_list(app):
    """Test populating table with empty FOV list."""
    table = FOVTable()
    table.populate_from_fov_list([])
    
    assert table.rowCount() == 0


def test_clear_table(app, sample_fov_infos):
    """Test clearing table data."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    # Verify data is present
    assert table.rowCount() == 3
    
    # Clear and verify
    table.clear_table()
    assert table.rowCount() == 0


def test_get_selected_fov_info(app, sample_fov_infos):
    """Test getting selected FOV info."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    # No selection initially
    assert table.get_selected_fov_info() is None
    
    # Select first row
    table.selectRow(0)
    selected_fov = table.get_selected_fov_info()
    assert selected_fov is not None
    assert selected_fov.index == 0
    assert selected_fov.cell_count == 45


def test_get_all_fov_infos(app, sample_fov_infos):
    """Test getting all FOV infos from table."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    all_fovs = table.get_all_fov_infos()
    assert len(all_fovs) == 3
    assert all_fovs[0].index == 0
    assert all_fovs[1].index == 1
    assert all_fovs[2].index == 2


def test_get_total_cell_count(app, sample_fov_infos):
    """Test getting total cell count."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    total = table.get_total_cell_count()
    assert total == 45 + 52 + 38  # 135


def test_get_fov_count(app, sample_fov_infos):
    """Test getting FOV count."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    count = table.get_fov_count()
    assert count == 3


def test_data_storage_in_items(app, sample_fov_infos):
    """Test that FOVInfo objects are properly stored in table items."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    # Check that FOVInfo is stored in UserRole
    item = table.item(0, 0)
    stored_fov = item.data(Qt.ItemDataRole.UserRole)
    assert isinstance(stored_fov, FOVInfo)
    assert stored_fov.index == 0
    assert stored_fov.cell_count == 45
    assert stored_fov.file_path == Path("test_fov0000_traces.csv")


def test_text_alignment(app, sample_fov_infos):
    """Test that table items are center-aligned."""
    table = FOVTable()
    table.populate_from_fov_list(sample_fov_infos)
    
    # Check alignment of items
    index_item = table.item(0, 0)
    count_item = table.item(0, 1)
    
    assert index_item.textAlignment() == Qt.AlignmentFlag.AlignCenter
    assert count_item.textAlignment() == Qt.AlignmentFlag.AlignCenter
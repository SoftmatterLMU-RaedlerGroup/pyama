"""
Tests for the StatisticsWidget component.
"""

import pytest
from unittest.mock import Mock
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from pyama_qt.merge.ui.widgets.statistics import StatisticsWidget
from pyama_qt.merge.services.merge import SampleGroup
from pyama_qt.merge.services.discovery import FOVInfo
from pathlib import Path


@pytest.fixture
def app():
    """Create QApplication instance for testing."""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture
def statistics_widget(app):
    """Create StatisticsWidget instance for testing."""
    widget = StatisticsWidget()
    return widget


@pytest.fixture
def sample_fov_infos():
    """Create sample FOVInfo objects for testing."""
    return [
        FOVInfo(index=0, cell_count=45, file_path=Path("fov_0000.csv"), has_quality_data=True),
        FOVInfo(index=1, cell_count=52, file_path=Path("fov_0001.csv"), has_quality_data=True),
        FOVInfo(index=2, cell_count=38, file_path=Path("fov_0002.csv"), has_quality_data=False),
        FOVInfo(index=3, cell_count=41, file_path=Path("fov_0003.csv"), has_quality_data=True),
        FOVInfo(index=4, cell_count=49, file_path=Path("fov_0004.csv"), has_quality_data=True),
    ]


@pytest.fixture
def valid_sample_group():
    """Create a valid sample group for testing."""
    return SampleGroup(
        name="Sample_1",
        fov_ranges="0-2,4",
        resolved_fovs=[0, 1, 2, 4]
    )


@pytest.fixture
def invalid_sample_group():
    """Create an invalid sample group for testing."""
    return SampleGroup(
        name="Invalid_Sample",
        fov_ranges="0-2,10,15-20",  # FOVs 10, 15-20 don't exist
        resolved_fovs=[0, 1, 2, 10, 15, 16, 17, 18, 19, 20]
    )


class TestStatisticsWidget:
    """Test cases for StatisticsWidget."""
    
    def test_initialization(self, statistics_widget):
        """Test widget initialization."""
        assert statistics_widget.available_fovs == []
        assert statistics_widget.fov_info_map == {}
        assert statistics_widget.current_sample is None
        
    def test_set_available_fovs(self, statistics_widget, sample_fov_infos):
        """Test setting available FOVs."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        
        expected_indices = [0, 1, 2, 3, 4]
        assert statistics_widget.available_fovs == expected_indices
        
        # Check FOV info mapping
        assert len(statistics_widget.fov_info_map) == 5
        assert statistics_widget.fov_info_map[0].cell_count == 45
        assert statistics_widget.fov_info_map[1].cell_count == 52
        
    def test_update_sample_statistics_none(self, statistics_widget):
        """Test updating statistics with None sample."""
        statistics_widget.update_sample_statistics(None)
        assert statistics_widget.current_sample is None
        
    def test_update_sample_statistics_valid(self, statistics_widget, sample_fov_infos, valid_sample_group):
        """Test updating statistics with valid sample group."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        statistics_widget.update_sample_statistics(valid_sample_group)
        
        assert statistics_widget.current_sample == valid_sample_group
        
        # Get summary to verify calculations
        summary = statistics_widget.get_current_sample_summary()
        assert summary is not None
        assert summary['name'] == "Sample_1"
        assert summary['fov_ranges'] == "0-2,4"
        assert summary['resolved_fovs'] == [0, 1, 2, 4]
        assert summary['fov_count'] == 4
        assert summary['total_cells'] == 45 + 52 + 38 + 49  # 184
        assert summary['is_valid'] is True
        assert summary['errors'] == []
        
    def test_update_sample_statistics_invalid(self, statistics_widget, sample_fov_infos, invalid_sample_group):
        """Test updating statistics with invalid sample group."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        statistics_widget.update_sample_statistics(invalid_sample_group)
        
        assert statistics_widget.current_sample == invalid_sample_group
        
        # Get summary to verify error handling
        summary = statistics_widget.get_current_sample_summary()
        assert summary is not None
        assert summary['name'] == "Invalid_Sample"
        assert summary['is_valid'] is False
        assert len(summary['errors']) > 0
        assert "FOV indices not available" in summary['errors'][0]
        
    def test_clear_statistics(self, statistics_widget, sample_fov_infos, valid_sample_group):
        """Test clearing statistics."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        statistics_widget.update_sample_statistics(valid_sample_group)
        
        # Verify sample is set
        assert statistics_widget.current_sample is not None
        
        # Clear and verify
        statistics_widget.clear_statistics()
        assert statistics_widget.current_sample is None
        
        summary = statistics_widget.get_current_sample_summary()
        assert summary is None
        
    def test_get_current_sample_summary_none(self, statistics_widget):
        """Test getting summary when no sample is selected."""
        summary = statistics_widget.get_current_sample_summary()
        assert summary is None
        
    def test_empty_fov_ranges(self, statistics_widget, sample_fov_infos):
        """Test handling of empty FOV ranges."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        
        empty_sample = SampleGroup(
            name="Empty_Sample",
            fov_ranges="",
            resolved_fovs=[]
        )
        
        statistics_widget.update_sample_statistics(empty_sample)
        
        summary = statistics_widget.get_current_sample_summary()
        assert summary is not None
        assert summary['fov_count'] == 0
        assert summary['total_cells'] == 0
        assert summary['resolved_fovs'] == []
        
    def test_large_fov_list_display(self, statistics_widget):
        """Test display with large number of FOVs."""
        # Create many FOVs
        many_fovs = [
            FOVInfo(index=i, cell_count=10+i, file_path=Path(f"fov_{i:04d}.csv"), has_quality_data=True)
            for i in range(20)
        ]
        
        statistics_widget.set_available_fovs(many_fovs)
        
        large_sample = SampleGroup(
            name="Large_Sample",
            fov_ranges="0-19",
            resolved_fovs=list(range(20))
        )
        
        statistics_widget.update_sample_statistics(large_sample)
        
        summary = statistics_widget.get_current_sample_summary()
        assert summary is not None
        assert summary['fov_count'] == 20
        assert len(summary['resolved_fovs']) == 20
        
    def test_missing_fov_info(self, statistics_widget, sample_fov_infos):
        """Test handling when some FOV info is missing."""
        statistics_widget.set_available_fovs(sample_fov_infos)
        
        # Create sample that references FOVs beyond what we have info for
        sample_with_missing = SampleGroup(
            name="Missing_Info_Sample",
            fov_ranges="0-1",  # Valid FOVs
            resolved_fovs=[0, 1]
        )
        
        # Remove one FOV from the info map to simulate missing info
        del statistics_widget.fov_info_map[1]
        
        statistics_widget.update_sample_statistics(sample_with_missing)
        
        summary = statistics_widget.get_current_sample_summary()
        assert summary is not None
        assert summary['fov_count'] == 2
        # Should only count cells from FOV 0 (45 cells)
        assert summary['total_cells'] == 45


if __name__ == "__main__":
    pytest.main([__file__])
"""Tests for the MergeService class."""

import pytest
import pandas as pd
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from pyama_qt.merge.services.merge import MergeService, SampleGroup


class TestSampleGroup:
    """Test the SampleGroup dataclass."""
    
    def test_sample_group_creation(self):
        """Test basic SampleGroup creation."""
        sample = SampleGroup(
            name="Test_Sample",
            fov_ranges="1-3,5",
            resolved_fovs=[1, 2, 3, 5],
            total_cells=100
        )
        
        assert sample.name == "Test_Sample"
        assert sample.fov_ranges == "1-3,5"
        assert sample.resolved_fovs == [1, 2, 3, 5]
        assert sample.total_cells == 100
        assert sample.fov_data == {}
    
    def test_sample_group_post_init(self):
        """Test SampleGroup post-init defaults."""
        sample = SampleGroup(name="Test", fov_ranges="1,2")
        
        assert sample.resolved_fovs == []
        assert sample.fov_data == {}
        assert sample.total_cells == 0


class TestMergeService:
    """Test the MergeService class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.merge_service = MergeService(frames_per_hour=12.0)
    
    def test_merge_service_initialization(self):
        """Test MergeService initialization."""
        service = MergeService(frames_per_hour=10.0)
        assert service.frames_per_hour == 10.0
        assert service.processing_loader is not None
        assert service.analysis_writer is not None
    
    def test_create_sample_group_valid(self):
        """Test creating a valid sample group."""
        available_fovs = [0, 1, 2, 3, 4, 5]
        
        sample = self.merge_service.create_sample_group(
            name="Sample_1",
            fov_ranges="1-3,5",
            available_fovs=available_fovs
        )
        
        assert sample.name == "Sample_1"
        assert sample.fov_ranges == "1-3,5"
        assert sample.resolved_fovs == [1, 2, 3, 5]
    
    def test_create_sample_group_invalid_ranges(self):
        """Test creating sample group with invalid FOV ranges."""
        available_fovs = [0, 1, 2, 3]
        
        with pytest.raises(ValueError, match="Invalid FOV ranges"):
            self.merge_service.create_sample_group(
                name="Sample_1",
                fov_ranges="1-5",  # FOV 4,5 not available
                available_fovs=available_fovs
            )
    
    @patch('pyama_qt.merge.services.merge.ProcessingCSVLoader')
    def test_load_fov_data(self, mock_loader_class):
        """Test loading FOV data for a sample group."""
        # Setup mock
        mock_loader = Mock()
        mock_loader_class.return_value = mock_loader
        
        # Create test DataFrame
        test_df = pd.DataFrame({
            'fov': [0, 0, 0, 1, 1, 1],
            'cell_id': [0, 1, 0, 0, 1, 0],
            'frame': [0, 0, 1, 0, 0, 1],
            'intensity_total': [100, 200, 110, 150, 250, 160],
            'area': [10, 20, 11, 15, 25, 16],
            'x_centroid': [5, 10, 5, 7, 12, 7],
            'y_centroid': [5, 10, 5, 8, 13, 8],
            'good': [True, True, True, True, True, True]
        })
        
        mock_loader.load_fov_traces.return_value = test_df
        mock_loader.filter_good_traces.return_value = test_df
        
        # Create sample group
        sample = SampleGroup(
            name="Test_Sample",
            fov_ranges="0,1",
            resolved_fovs=[0, 1]
        )
        
        # Create file paths
        fov_file_paths = {
            0: Path("fov_0.csv"),
            1: Path("fov_1.csv")
        }
        
        # Test loading
        service = MergeService()
        service.load_fov_data(sample, fov_file_paths)
        
        # Verify results
        assert len(sample.fov_data) == 2
        assert 0 in sample.fov_data
        assert 1 in sample.fov_data
        assert sample.total_cells == 4  # 2 unique cells per FOV
    
    def test_merge_sample_data(self):
        """Test merging sample data to analysis format."""
        # Create sample group with mock data
        sample = SampleGroup(
            name="Test_Sample",
            fov_ranges="0,1",
            resolved_fovs=[0, 1]
        )
        
        # Create test FOV data
        fov_0_data = pd.DataFrame({
            'cell_id': [0, 1, 0, 1],
            'frame': [0, 0, 12, 12],  # 0 and 1 hour
            'intensity_total': [100, 200, 110, 210]
        })
        
        fov_1_data = pd.DataFrame({
            'cell_id': [0, 1, 0, 1],
            'frame': [0, 0, 12, 12],  # 0 and 1 hour
            'intensity_total': [150, 250, 160, 260]
        })
        
        sample.fov_data = {0: fov_0_data, 1: fov_1_data}
        
        # Test merging
        result_df = self.merge_service.merge_sample_data(sample)
        
        # Verify structure
        assert result_df.index.name == 'time'
        assert len(result_df.columns) == 4  # 2 cells from each FOV
        assert list(result_df.columns) == [0, 1, 2, 3]  # Sequential cell IDs
        
        # Verify time conversion (frames_per_hour = 12)
        expected_times = [0.0, 1.0]
        assert list(result_df.index) == expected_times
        
        # Verify cell renumbering and data
        # FOV 0: cells 0,1 -> sequential IDs 0,1
        # FOV 1: cells 0,1 -> sequential IDs 2,3
        assert result_df.loc[0.0, 0] == 100  # FOV 0, cell 0, frame 0
        assert result_df.loc[0.0, 1] == 200  # FOV 0, cell 1, frame 0
        assert result_df.loc[0.0, 2] == 150  # FOV 1, cell 0, frame 0
        assert result_df.loc[0.0, 3] == 250  # FOV 1, cell 1, frame 0
    
    def test_merge_sample_data_no_data(self):
        """Test merging with no FOV data."""
        sample = SampleGroup(
            name="Empty_Sample",
            fov_ranges="0",
            resolved_fovs=[0]
        )
        
        with pytest.raises(ValueError, match="No FOV data loaded"):
            self.merge_service.merge_sample_data(sample)
    
    @patch('pyama_qt.merge.services.merge.AnalysisCSVWriter')
    def test_export_sample_csv(self, mock_writer_class):
        """Test exporting sample to CSV."""
        # Setup mock
        mock_writer = Mock()
        mock_writer_class.return_value = mock_writer
        
        # Create sample with data
        sample = SampleGroup(
            name="Test_Sample",
            fov_ranges="0",
            resolved_fovs=[0]
        )
        
        sample.fov_data = {0: pd.DataFrame({
            'cell_id': [0, 1],
            'frame': [0, 0],
            'intensity_total': [100, 200]
        })}
        
        # Test export
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            service = MergeService()
            
            result_path = service.export_sample_csv(sample, output_dir)
            
            # Verify result
            expected_path = output_dir / "Test_Sample.csv"
            assert result_path == expected_path
            
            # Verify writer was called
            mock_writer.write_sample_data.assert_called_once()
    
    def test_validate_sample_groups(self):
        """Test validation of sample groups."""
        # Create test sample groups
        sample1 = SampleGroup(name="Sample_1", fov_ranges="0,1", resolved_fovs=[0, 1])
        sample2 = SampleGroup(name="Sample_2", fov_ranges="2,3", resolved_fovs=[2, 3])
        sample3 = SampleGroup(name="Sample_1", fov_ranges="4", resolved_fovs=[4])  # Duplicate name
        sample4 = SampleGroup(name="Sample_4", fov_ranges="1,5", resolved_fovs=[1, 5])  # FOV conflict
        sample5 = SampleGroup(name="Empty", fov_ranges="", resolved_fovs=[])  # Empty
        
        available_fovs = [0, 1, 2, 3, 4, 5]
        
        errors = self.merge_service.validate_sample_groups(
            [sample1, sample2, sample3, sample4, sample5],
            available_fovs
        )
        
        # Should have 3 errors: duplicate name, FOV conflict, empty sample
        assert len(errors) == 3
        assert any("Duplicate sample names" in error for error in errors)
        assert any("FOV 1 assigned to both" in error for error in errors)
        assert any("Samples with no assigned FOVs" in error for error in errors)
    
    def test_get_merge_statistics(self):
        """Test getting merge statistics."""
        # Create test sample groups
        sample1 = SampleGroup(name="Sample_1", fov_ranges="0,1", resolved_fovs=[0, 1], total_cells=50)
        sample2 = SampleGroup(name="Sample_2", fov_ranges="2,3", resolved_fovs=[2, 3], total_cells=75)
        
        # Add some mock data
        sample1.fov_data = {0: pd.DataFrame(), 1: pd.DataFrame()}
        
        stats = self.merge_service.get_merge_statistics([sample1, sample2])
        
        # Verify overall statistics
        assert stats['sample_count'] == 2
        assert stats['total_fovs'] == 4
        assert stats['total_cells'] == 125
        
        # Verify sample-specific statistics
        assert len(stats['samples']) == 2
        
        sample1_stats = stats['samples'][0]
        assert sample1_stats['name'] == 'Sample_1'
        assert sample1_stats['fov_count'] == 2
        assert sample1_stats['fov_indices'] == [0, 1]
        assert sample1_stats['cell_count'] == 50
        assert sample1_stats['has_data'] == True
        
        sample2_stats = stats['samples'][1]
        assert sample2_stats['name'] == 'Sample_2'
        assert sample2_stats['fov_count'] == 2
        assert sample2_stats['fov_indices'] == [2, 3]
        assert sample2_stats['cell_count'] == 75
        assert sample2_stats['has_data'] == False


if __name__ == '__main__':
    pytest.main([__file__])
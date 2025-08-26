"""
Tests for FOV discovery service.
"""

import pytest
import pandas as pd
from pathlib import Path
import tempfile
import shutil

from pyama_qt.merge.services.discovery import FOVDiscoveryService, FOVInfo


class TestFOVDiscoveryService:
    """Test cases for FOVDiscoveryService."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.service = FOVDiscoveryService()
        self.temp_dir = Path(tempfile.mkdtemp())
        
    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)
    
    def create_test_csv(self, filename: str, fov_index: int, cell_count: int, has_good_column: bool = False):
        """Create a test CSV file with trace data."""
        data = []
        for cell_id in range(cell_count):
            for frame in range(10):  # 10 time points
                row = {
                    'fov': fov_index,
                    'cell_id': cell_id,
                    'frame': frame,
                    'intensity_total': 1000.0 + cell_id * 100 + frame * 10,
                    'area': 50.0 + cell_id * 5,
                    'x_centroid': 100.0 + cell_id * 10,
                    'y_centroid': 200.0 + cell_id * 15
                }
                if has_good_column:
                    row['good'] = True
                data.append(row)
        
        df = pd.DataFrame(data)
        csv_path = self.temp_dir / filename
        df.to_csv(csv_path, index=False)
        return csv_path
    
    def test_discover_fov_files_basic(self):
        """Test basic FOV file discovery."""
        # Create test files
        self.create_test_csv("test_fov0000_traces.csv", 0, 5)
        self.create_test_csv("test_fov0001_traces.csv", 1, 3)
        self.create_test_csv("test_fov0002_traces.csv", 2, 7)
        
        # Discover files
        fov_infos = self.service.discover_fov_files(self.temp_dir)
        
        # Verify results
        assert len(fov_infos) == 3
        assert fov_infos[0].index == 0
        assert fov_infos[0].cell_count == 5
        assert fov_infos[1].index == 1
        assert fov_infos[1].cell_count == 3
        assert fov_infos[2].index == 2
        assert fov_infos[2].cell_count == 7
    
    def test_prioritize_inspected_files(self):
        """Test that inspected files are prioritized over regular files."""
        # Create both regular and inspected files
        self.create_test_csv("test_fov0000_traces.csv", 0, 5)
        self.create_test_csv("test_fov0000_traces_inspected.csv", 0, 4, has_good_column=True)
        self.create_test_csv("test_fov0001_traces.csv", 1, 3)
        
        # Discover files
        fov_infos = self.service.discover_fov_files(self.temp_dir)
        
        # Verify inspected file is used for FOV 0
        assert len(fov_infos) == 2
        fov_0 = next(fov for fov in fov_infos if fov.index == 0)
        assert fov_0.cell_count == 4  # From inspected file
        assert fov_0.has_quality_data == True
        assert "inspected" in fov_0.file_path.name
    
    def test_load_fov_metadata(self):
        """Test loading metadata from a single FOV file."""
        csv_path = self.create_test_csv("test_fov0005_traces.csv", 5, 8)
        
        fov_info = self.service.load_fov_metadata(csv_path)
        
        assert fov_info.index == 5
        assert fov_info.cell_count == 8
        assert fov_info.frame_count == 10
        assert fov_info.has_quality_data == False
        assert fov_info.file_path == csv_path
    
    def test_discover_empty_directory(self):
        """Test discovery in empty directory raises appropriate error."""
        with pytest.raises(ValueError, match="No trace CSV files found"):
            self.service.discover_fov_files(self.temp_dir)
    
    def test_discover_nonexistent_directory(self):
        """Test discovery with nonexistent directory raises appropriate error."""
        nonexistent = Path("/nonexistent/directory")
        with pytest.raises(FileNotFoundError):
            self.service.discover_fov_files(nonexistent)
    
    def test_validate_fov_continuity(self):
        """Test FOV continuity validation."""
        # Create continuous FOVs
        fov_infos = [
            FOVInfo(0, 5, Path("fov0.csv"), False, 10),
            FOVInfo(1, 3, Path("fov1.csv"), False, 10),
            FOVInfo(2, 7, Path("fov2.csv"), False, 10)
        ]
        
        assert self.service.validate_fov_continuity(fov_infos) == True
        
        # Create non-continuous FOVs
        fov_infos_gap = [
            FOVInfo(0, 5, Path("fov0.csv"), False, 10),
            FOVInfo(2, 7, Path("fov2.csv"), False, 10)  # Missing FOV 1
        ]
        
        assert self.service.validate_fov_continuity(fov_infos_gap) == False
    
    def test_get_summary_stats(self):
        """Test summary statistics calculation."""
        fov_infos = [
            FOVInfo(0, 5, Path("fov0.csv"), True, 10),
            FOVInfo(1, 3, Path("fov1.csv"), False, 10),
            FOVInfo(2, 7, Path("fov2.csv"), True, 10)
        ]
        
        stats = self.service.get_summary_stats(fov_infos)
        
        assert stats['total_fovs'] == 3
        assert stats['total_cells'] == 15
        assert stats['files_with_quality_data'] == 2
        assert stats['min_cells_per_fov'] == 3
        assert stats['max_cells_per_fov'] == 7
        assert stats['avg_cells_per_fov'] == 5
    
    def test_get_summary_stats_empty(self):
        """Test summary statistics with empty list."""
        stats = self.service.get_summary_stats([])
        
        assert stats['total_fovs'] == 0
        assert stats['total_cells'] == 0
        assert stats['files_with_quality_data'] == 0
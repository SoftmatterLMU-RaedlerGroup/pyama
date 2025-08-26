"""Tests for FOV range parsing utilities."""

import pytest
from pyama_qt.merge.utils.fov_parser import (
    parse_fov_ranges,
    validate_fov_ranges,
    get_fov_range_summary,
    check_fov_conflicts
)


class TestParseFovRanges:
    """Test FOV range parsing functionality."""
    
    def test_empty_string(self):
        """Test parsing empty or whitespace-only strings."""
        assert parse_fov_ranges("") == []
        assert parse_fov_ranges("   ") == []
    
    def test_single_fov(self):
        """Test parsing single FOV indices."""
        assert parse_fov_ranges("5") == [5]
        assert parse_fov_ranges("0") == [0]
        assert parse_fov_ranges("  3  ") == [3]
    
    def test_multiple_fovs(self):
        """Test parsing comma-separated FOV indices."""
        assert parse_fov_ranges("1,3,5") == [1, 3, 5]
        assert parse_fov_ranges("5,1,3") == [1, 3, 5]  # Should be sorted
        assert parse_fov_ranges("0,2,4,6") == [0, 2, 4, 6]
    
    def test_simple_range(self):
        """Test parsing simple ranges."""
        assert parse_fov_ranges("1-5") == [1, 2, 3, 4, 5]
        assert parse_fov_ranges("0-3") == [0, 1, 2, 3]
        assert parse_fov_ranges("7-7") == [7]  # Single element range
    
    def test_mixed_notation(self):
        """Test parsing mixed range and individual notation."""
        assert parse_fov_ranges("1-4,6,9-11") == [1, 2, 3, 4, 6, 9, 10, 11]
        assert parse_fov_ranges("0,2-4,7") == [0, 2, 3, 4, 7]
    
    def test_duplicate_removal(self):
        """Test that duplicates are removed."""
        assert parse_fov_ranges("1,2,1-3") == [1, 2, 3]
        assert parse_fov_ranges("5,3-7,6") == [3, 4, 5, 6, 7]
    
    def test_invalid_formats(self):
        """Test error handling for invalid formats."""
        with pytest.raises(ValueError, match="Invalid FOV index"):
            parse_fov_ranges("abc")
        
        with pytest.raises(ValueError, match="Invalid range format"):
            parse_fov_ranges("1-")
        
        with pytest.raises(ValueError, match="Invalid range format"):
            parse_fov_ranges("-5")
        
        with pytest.raises(ValueError, match="Invalid range"):
            parse_fov_ranges("5-3")  # Start > end


class TestValidateFovRanges:
    """Test FOV range validation functionality."""
    
    def test_valid_ranges(self):
        """Test validation of valid ranges."""
        available = [0, 1, 2, 3, 4, 5]
        
        is_valid, errors = validate_fov_ranges("1-3,5", available)
        assert is_valid is True
        assert errors == []
        
        is_valid, errors = validate_fov_ranges("", available)
        assert is_valid is True
        assert errors == []
    
    def test_missing_fovs(self):
        """Test validation when requested FOVs are not available."""
        available = [0, 1, 2, 3]
        
        is_valid, errors = validate_fov_ranges("1-5", available)
        assert is_valid is False
        assert "FOV indices not available: [4, 5]" in errors[0]
    
    def test_invalid_format(self):
        """Test validation with invalid format."""
        available = [0, 1, 2, 3]
        
        is_valid, errors = validate_fov_ranges("1-", available)
        assert is_valid is False
        assert "Invalid range format" in errors[0]


class TestGetFovRangeSummary:
    """Test FOV range summary functionality."""
    
    def test_valid_summary(self):
        """Test summary for valid ranges."""
        available = [0, 1, 2, 3, 4, 5]
        summary = get_fov_range_summary("1-3,5", available)
        
        assert summary['valid'] is True
        assert summary['resolved_fovs'] == [1, 2, 3, 5]
        assert summary['count'] == 4
        assert summary['errors'] == []
    
    def test_invalid_summary(self):
        """Test summary for invalid ranges."""
        available = [0, 1, 2]
        summary = get_fov_range_summary("1-5", available)
        
        assert summary['valid'] is False
        assert summary['resolved_fovs'] == []
        assert summary['count'] == 0
        assert len(summary['errors']) > 0


class TestCheckFovConflicts:
    """Test FOV conflict detection functionality."""
    
    def test_no_conflicts(self):
        """Test when there are no conflicts."""
        sample_ranges = [
            ("Sample1", "0-2"),
            ("Sample2", "3-5"),
            ("Sample3", "6,8")
        ]
        available = list(range(10))
        
        errors = check_fov_conflicts(sample_ranges, available)
        assert errors == []
    
    def test_with_conflicts(self):
        """Test when there are conflicts."""
        sample_ranges = [
            ("Sample1", "0-3"),
            ("Sample2", "2-5"),  # Conflict on FOVs 2,3
            ("Sample3", "5,7")   # Conflict on FOV 5
        ]
        available = list(range(10))
        
        errors = check_fov_conflicts(sample_ranges, available)
        assert len(errors) == 3  # FOVs 2, 3, and 5 have conflicts
        assert any("FOV 2 assigned to both" in error for error in errors)
        assert any("FOV 3 assigned to both" in error for error in errors)
        assert any("FOV 5 assigned to both" in error for error in errors)
    
    def test_empty_ranges(self):
        """Test with empty ranges."""
        sample_ranges = [
            ("Sample1", "0-2"),
            ("Sample2", ""),  # Empty range
            ("Sample3", "3-5")
        ]
        available = list(range(10))
        
        errors = check_fov_conflicts(sample_ranges, available)
        assert errors == []
"""
Unit tests for processing services.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import numpy as np
from pathlib import Path
import sys
import tempfile
import shutil

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from pyama_qt.services.binarization import BinarizationService
from pyama_qt.services.base import BaseProcessingService


class TestBinarizationService(unittest.TestCase):
    """Test BinarizationService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = BinarizationService()
        self.temp_dir = Path(tempfile.mkdtemp())
        
        # Mock data_info structure
        self.mock_data_info = {
            'filepath': '/path/to/test.nd2',
            'filename': 'test.nd2',
            'pc_channel': 0,
            'metadata': {
                'n_frames': 10,
                'height': 100,
                'width': 100,
                'n_fov': 2
            }
        }
        
        # Mock parameters
        self.mock_params = {
            'mask_size': 3,
            'binarization_method': 'log_std'  # For testing purposes only
        }
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_step_name(self):
        """Test step name property."""
        self.assertEqual(self.service.get_step_name(), "Binarization")
    
    def test_get_expected_outputs(self):
        """Test expected output file generation."""
        outputs = self.service.get_expected_outputs(self.mock_data_info, self.temp_dir)
        
        self.assertIsInstance(outputs, dict)
        self.assertIn('binarized', outputs)
        self.assertIn('phase_contrast', outputs)
        
        # Should have 2 files per type (n_fov = 2)
        self.assertEqual(len(outputs['binarized']), 2)
        self.assertEqual(len(outputs['phase_contrast']), 2)
        
        # Check file naming pattern
        binarized_file = outputs['binarized'][0]
        self.assertTrue(str(binarized_file).endswith('_fov00_binarized.npz'))
    
    @patch('pyama_qt.services.binarization.ND2Reader')
    def test_process_fov_mock(self, mock_nd2_reader):
        """Test FOV processing with mocked ND2Reader."""
        # Mock ND2Reader context manager
        mock_images = MagicMock()
        mock_nd2_reader.return_value.__enter__ = Mock(return_value=mock_images)
        mock_nd2_reader.return_value.__exit__ = Mock(return_value=None)
        
        # Mock frame data
        test_frame = np.random.randint(0, 255, (100, 100), dtype=np.uint16)
        mock_images.__getitem__ = Mock(return_value=test_frame)
        
        # Mock memmap creation
        with patch.object(self.service, 'create_memmap_array') as mock_memmap:
            mock_binarized = np.zeros((10, 100, 100), dtype=np.bool_)
            mock_phase = np.zeros((10, 100, 100), dtype=np.uint16)
            mock_memmap.side_effect = [mock_binarized, mock_phase]
            
            # Test processing
            result = self.service.process_fov(
                nd2_path='/path/to/test.nd2',
                fov_index=0,
                data_info=self.mock_data_info,
                output_dir=self.temp_dir,
                params=self.mock_params
            )
            
            self.assertTrue(result)
            self.assertEqual(mock_memmap.call_count, 2)  # Called for both binarized and phase contrast
    
    def test_signal_emissions(self):
        """Test that service emits appropriate signals."""
        # Track signal emissions
        progress_signals = []
        status_signals = []
        error_signals = []
        
        self.service.progress_updated.connect(progress_signals.append)
        self.service.status_updated.connect(status_signals.append)
        self.service.error_occurred.connect(error_signals.append)
        
        # Test signal emission methods
        self.service.progress_updated.emit(50)
        self.service.status_updated.emit("Test status")
        self.service.error_occurred.emit("Test error")
        
        self.assertEqual(progress_signals, [50])
        self.assertEqual(status_signals, ["Test status"])
        self.assertEqual(error_signals, ["Test error"])


class TestBaseProcessingService(unittest.TestCase):
    """Test BaseProcessingService functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.service = BaseProcessingService()
        self.temp_dir = Path(tempfile.mkdtemp())
    
    def tearDown(self):
        """Clean up test fixtures."""
        shutil.rmtree(self.temp_dir)
    
    def test_output_filename_generation(self):
        """Test output filename generation."""
        filename = self.service.get_output_filename("test_file", 5, "binarized")
        self.assertEqual(filename, "test_file_fov05_binarized.npz")
    
    def test_memmap_creation(self):
        """Test memory-mapped array creation."""
        output_path = self.temp_dir / "test_memmap.npz"
        shape = (10, 50, 50)
        dtype = np.bool_
        
        memmap_array = self.service.create_memmap_array(shape, dtype, output_path)
        
        self.assertEqual(memmap_array.shape, shape)
        self.assertEqual(memmap_array.dtype, dtype)
        self.assertTrue(output_path.exists())


if __name__ == '__main__':
    unittest.main()
# PyAMA-Qt Tests

This directory contains tests for the PyAMA-Qt microscopy image analysis application.

## Test Structure

```
tests/
├── __init__.py
├── README.md
├── binarization/                    # Binarization algorithm testing
│   ├── __init__.py
│   ├── main.py                      # Interactive testing script
│   └── utils.py                     # Testing utilities
└── test_services.py                # Unit tests for processing services
```

## Running Tests

### Unit Tests

```bash
# Run unit tests
python -m pytest tests/test_services.py

# Run with verbose output
python -m pytest tests/test_services.py -v

# Alternative: using unittest
python tests/test_services.py
```

### Interactive Binarization Testing

Test different binarization algorithms on single TIFF frames:

```bash
# Test a single frame
python tests/binarization/main.py path/to/your/test_frame.tif

# Example with phase contrast frame
python tests/binarization/main.py data/phase_contrast_sample.tif
```

This will:
- Test all available binarization methods
- Generate comparison plots
- Perform parameter sweeps
- Save results to the same directory as your input image

## Test Data

For testing, you can use:
- Single TIFF frames exported from your ND2 files
- Synthetic test images (created automatically in unit tests)
- Phase contrast microscopy images

## Available Binarization Methods

The testing framework supports these methods:

1. **`log_std`** - Logarithmic standard deviation (best for phase contrast)
2. **`otsu`** - Otsu's method
3. **`adaptive`** - Adaptive thresholding
4. **`edge`** - Edge-based binarization
5. **`local`** - Local statistics-based thresholding

## Test Coverage

### Service Tests (`test_services.py`)
- BinarizationService processing logic
- Signal emissions
- File I/O operations
- Memory-mapped array handling

### Interactive Tests (`test_binarization.py`)
- Visual comparison of methods
- Parameter sweeps
- Real image testing
- Performance evaluation

## Adding New Tests

### For New Services
Add tests to `test_services.py`:

```python
class TestNewService(unittest.TestCase):
    """Test new processing service."""
    
    def setUp(self):
        self.service = NewService()
    
    def test_service_functionality(self):
        # Test service methods
        pass
```

## Dependencies

Tests require:
- `numpy`
- `matplotlib` (for visualization tests)
- `PIL` (for image loading)
- `scipy`
- `scikit-image`
- `pytest` (optional, for test runner)

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running from the project root:
```bash
cd /path/to/pyama-qt
python tests/test_algorithms.py
```

### Missing Test Images
For interactive testing, you need actual image files. You can:
1. Export frames from ImageJ/Fiji: File → Export → TIFF
2. Use the synthetic images created in unit tests
3. Convert ND2 frames to TIFF using your preferred tool

### Memory Issues
For large test images, the tests create temporary files in `/tmp/`. Clean up with:
```bash
# On macOS/Linux
rm -rf /tmp/tmp*
```
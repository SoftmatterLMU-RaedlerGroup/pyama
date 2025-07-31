# PyAMA-Qt Tests

This directory contains tests for the PyAMA-Qt microscopy image analysis application.

## Test Structure

```
tests/
├── __init__.py
├── README.md
└── test_modules.py                  # Module testing script
```

## Running Tests

### Module Testing

The test script is configured with constants at the top of the file. To use:

1. Open `tests/test_modules.py` and update the configuration section:
   ```python
   # File paths
   ND2_FILE = Path("/path/to/your/data.nd2")  # UPDATE THIS
   OUTPUT_DIR = Path("/path/to/test/output")  # UPDATE THIS
   
   # FOV range
   FOV_START = 0  # Starting FOV index
   FOV_END = 2    # Ending FOV index
   
   # Test module to run
   TEST_MODULE = "binarization"  # Options: "binarization", "background", "traces", "workflow"
   ```

2. Run the test:
   ```bash
   # With uv
   uv run python tests/test_modules.py
   
   # Or if pyama_qt is installed
   python tests/test_modules.py
   ```

The script will automatically run the selected module with your configured parameters.


## Test Data

For testing, you can use:
- Single TIFF frames exported from your ND2 files
- Synthetic test images (created automatically in unit tests)
- Phase contrast microscopy images


## Dependencies

Tests require:
- `numpy`
- `matplotlib` (for visualization)
- `PIL` (for image loading)
- `scipy`
- `scikit-image`

## Troubleshooting

### Import Errors
If you get import errors, make sure you're running from the project root:
```bash
cd /path/to/pyama-qt
python tests/test_modules.py
```

### Missing Test Images
For module testing, you need ND2 files or single frame images:
1. Export frames from ImageJ/Fiji: File → Export → TIFF
2. Convert ND2 frames to TIFF using your preferred tool

### Memory Issues
For large test images, the tests create temporary files in `/tmp/`. Clean up with:
```bash
# On macOS/Linux
rm -rf /tmp/tmp*
```
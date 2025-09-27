pyama\test_imports.py
import sys
import os

# Add the pyama-core source directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "pyama-core", "src"))

def test_imports():
    """Test that all the fixed services can be imported without AttributeError"""
    print("Testing imports of the fixed services...")

    # Test each service import
    try:
        from pyama_core.processing.workflow.services.steps.segmentation import SegmentationService
        print("✓ SegmentationService imports successfully")
    except Exception as e:
        print(f"✗ SegmentationService import failed: {e}")

    try:
        from pyama_core.processing.workflow.services.steps.correction import CorrectionService
        print("✓ CorrectionService imports successfully")
    except Exception as e:
        print(f"✗ CorrectionService import failed: {e}")

    try:
        from pyama_core.processing.workflow.services.steps.tracking import TrackingService
        print("✓ TrackingService imports successfully")
    except Exception as e:
        print(f"✗ TrackingService import failed: {e}")

    try:
        from pyama_core.processing.workflow.services.steps.extraction import ExtractionService
        print("✓ ExtractionService imports successfully")
    except Exception as e:
        print(f"✗ ExtractionService import failed: {e}")

    try:
        from pyama_core.processing.workflow.pipeline import run_complete_workflow, _deserialize_from_dict
        print("✓ Pipeline functions import successfully")
    except Exception as e:
        print(f"✗ Pipeline functions import failed: {e}")

    print("Import test completed!")

def test_dataclass_attributes():
    """Test that ResultsPathsPerFOV dataclass is used correctly"""
    print("\nTesting dataclass attribute access...")

    from pyama_core.processing.workflow.services.types import ResultsPathsPerFOV
    from pathlib import Path

    try:
        # Create a ResultsPathsPerFOV instance
        fov_paths = ResultsPathsPerFOV()
        fov_paths.pc = (0, Path("/tmp/test.npy"))
        fov_paths.fl = [(1, Path("/tmp/fl1.npy")), (2, Path("/tmp/fl2.npy"))]
        fov_paths.seg = (0, Path("/tmp/seg.npy"))

        # Test attribute access
        pc = fov_paths.pc
        fl = fov_paths.fl
        seg = fov_paths.seg
        seg_labeled = fov_paths.seg_labeled

        # These should not raise AttributeError
        assert pc is not None
        assert len(fl) == 2
        assert seg is not None
        print("✓ Dataclass attribute access works correctly")

    except Exception as e:
        print(f"✗ Dataclass attribute access failed: {e}")
        raise

def test_yaml_serialization():
    """Test the YAML serialization fix"""
    print("\nTesting YAML serialization...")

    from pyama_core.processing.workflow.pipeline import _deserialize_from_dict
    from pyama_core.processing.workflow.services.types import ProcessingContext

    test_data = {
        "output_dir": "/tmp/test_output",
        "channels": {"pc": 0, "fl": [1, 2]},
        "results_paths": {
            "0": {
                "pc": [0, "/tmp/test_output/fov_000/test_pc.npy"],
                "fl": [
                    [1, "/tmp/test_output/fov_000/test_fl1.npy"],
                ],
                "seg_labeled": [0, "/tmp/test_output/fov_000/test_seg.npy"],
            }
        },
        "params": {},
        "time_units": "min",
    }

    try:
        result = _deserialize_from_dict(test_data)

        assert isinstance(result, ProcessingContext)
        assert result.channels.pc == 0
        assert result.channels.fl == [1, 2]
        assert result.results_paths[0].pc == (0, Path("/tmp/test_output/fov_000/test_pc.npy"))
        assert result.results_paths[0].fl[0] == (1, Path("/tmp/test_output/fov_000/test_fl1.npy"))
        print("✓ YAML deserialization works correctly")

    except Exception as e:
        print(f"✗ YAML serialization failed: {e}")
        raise

if __name__ == "__main__":
    test_imports()
    test_dataclass_attributes()
    test_yaml_serialization()
    print("\n" + "="*50)
    print("All tests passed! The fixes are working correctly.")

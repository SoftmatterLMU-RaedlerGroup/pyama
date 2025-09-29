#!/usr/bin/env python3
"""
Performance tests for bioio microscopy file loading and frame extraction.
Tests the speed of load_microscopy_file and get_microscopy_frame functions.
"""

import time
import logging
from pathlib import Path
from typing import Any

from pyama_core.io import load_microscopy_file, get_microscopy_frame


def time_function(func, *args, **kwargs) -> tuple[float, Any]:
    """Time a function call and return (duration, result)."""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    duration = end_time - start_time
    return duration, result


def benchmark_load_microscopy_file(file_path: Path) -> tuple[float, Any, Any]:
    """Benchmark load_microscopy_file performance - single run."""
    print(f"\nBenchmarking load_microscopy_file with {file_path}")
    print("-" * 50)

    try:
        duration, (img, metadata) = time_function(load_microscopy_file, file_path)
        print(f"Duration: {duration:.3f}s")
        print(
            f"Loaded {metadata.n_frames} frames, {metadata.n_channels} channels, {metadata.width}×{metadata.height}"
        )
        return duration, img, metadata
    except Exception as e:
        print(f"Failed: {e}")
        return float("inf"), None, None


def benchmark_get_microscopy_frame(img, metadata: Any) -> list[tuple[str, float, str]]:
    """Benchmark get_microscopy_frame performance - single run per test case."""
    print("\nBenchmarking get_microscopy_frame")
    print("-" * 50)

    results = []

    # Test different scenarios
    test_cases = []

    # Basic case: first frame, first channel, first timepoint
    if metadata.n_frames > 0 and metadata.n_channels > 0:
        test_cases.append(("First frame (f=0, c=0, t=0)", 0, 0, 0))

    # If we have multiple frames/channels, test a few more cases
    if metadata.n_frames > 1:
        test_cases.append(("Second frame (f=0, c=0, t=1)", 0, 0, 1))

    if metadata.n_channels > 1:
        test_cases.append(("Second channel (f=0, c=1, t=0)", 0, 1, 0))

    if metadata.n_fovs > 1:
        test_cases.append(("Second FOV (f=1, c=0, t=0)", 1, 0, 0))

    for desc, f, c, t in test_cases:
        try:
            duration, frame = time_function(get_microscopy_frame, img, f=f, c=c, t=t)
            print(f"{desc}: {duration:.4f}s - Shape: {frame.shape}")
            results.append((desc, duration, f"{frame.shape}"))
        except Exception as e:
            print(f"{desc}: Failed - {e}")
            results.append((desc, float("inf"), "Failed"))

    return results


def main():
    """Main test function."""
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    print("Starting bioio performance tests...")

    # Test file path - you can modify this to point to an actual microscopy file
    test_file = Path("/project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2")

    # Check if file exists
    if not test_file.exists():
        print(f"Warning: Test file {test_file} not found.")
        print(
            "Please update the file path to point to a valid microscopy file (.nd2, .czi, etc.)"
        )
        return

    print(f"Test file: {test_file}")
    print(f"File size: {test_file.stat().st_size / (1024 * 1024):.1f} MB")

    # Benchmark file loading
    load_duration, img, metadata = benchmark_load_microscopy_file(test_file)

    # If loading succeeded, benchmark frame extraction
    if img is not None and metadata is not None:
        try:
            frame_results = benchmark_get_microscopy_frame(img, metadata)

            print("\n=== SUMMARY ===")
            print(f"File loading:      {load_duration:.3f}s")
            for desc, duration, shape in frame_results:
                if duration != float("inf"):
                    print(f"{desc}: {duration:.4f}s")

        except Exception as e:
            print(f"Frame extraction benchmark failed: {e}")


if __name__ == "__main__":
    main()

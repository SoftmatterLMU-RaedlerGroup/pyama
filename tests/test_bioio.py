#!/usr/bin/env python3
"""
Performance tests for bioio microscopy file loading and frame extraction.
Tests the speed of load_microscopy_file and get_microscopy_frame functions.
"""

import time
import logging
from pathlib import Path
from typing import Any

from pyama_core.io import (
    load_microscopy_file,
    get_microscopy_frame,
    get_microscopy_channel_stack,
    get_microscopy_time_stack,
)


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


def benchmark_get_microscopy_channel_stack(
    img, metadata: Any
) -> list[tuple[str, float, str]]:
    """Benchmark get_microscopy_channel_stack performance - single run per test case."""
    print("\nBenchmarking get_microscopy_channel_stack")
    print("-" * 50)

    results = []

    # Test different scenarios
    test_cases = []

    # Basic case: first FOV, first timepoint
    if metadata.n_channels > 1 and metadata.n_fovs > 0 and metadata.n_frames > 0:
        test_cases.append(("Channel stack (f=0, t=0)", 0, 0))

    # If we have multiple FOVs, test another one
    if metadata.n_fovs > 1 and metadata.n_channels > 1 and metadata.n_frames > 0:
        test_cases.append(("Channel stack (f=1, t=0)", 1, 0))

    for desc, f, t in test_cases:
        try:
            duration, stack = time_function(get_microscopy_channel_stack, img, f=f, t=t)
            print(f"{desc}: {duration:.4f}s - Shape: {stack.shape}")
            results.append((desc, duration, f"{stack.shape}"))
        except Exception as e:
            print(f"{desc}: Failed - {e}")
            results.append((desc, float("inf"), "Failed"))

    return results


def benchmark_get_microscopy_time_stack(
    img, metadata: Any
) -> list[tuple[str, float, str]]:
    """Benchmark get_microscopy_time_stack performance - single run per test case."""
    print("\nBenchmarking get_microscopy_time_stack")
    print("-" * 50)

    results = []

    # Test different scenarios
    test_cases = []

    # Basic case: first FOV, first channel
    if metadata.n_frames > 1 and metadata.n_fovs > 0 and metadata.n_channels > 0:
        test_cases.append(("Time stack (f=0, c=0)", 0, 0))

    # If we have multiple FOVs, test another one
    if metadata.n_fovs > 1 and metadata.n_frames > 1 and metadata.n_channels > 0:
        test_cases.append(("Time stack (f=1, c=0)", 1, 0))

    # If we have multiple channels, test another one
    if metadata.n_channels > 1 and metadata.n_frames > 1 and metadata.n_fovs > 0:
        test_cases.append(("Time stack (f=0, c=1)", 0, 1))

    for desc, f, c in test_cases:
        try:
            duration, stack = time_function(get_microscopy_time_stack, img, f=f, c=c)
            print(f"{desc}: {duration:.4f}s - Shape: {stack.shape}")
            results.append((desc, duration, f"{stack.shape}"))
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
            channel_stack_results = benchmark_get_microscopy_channel_stack(
                img, metadata
            )
            time_stack_results = benchmark_get_microscopy_time_stack(img, metadata)

            print("\n=== SUMMARY ===")
            print(f"File loading:      {load_duration:.3f}s")

            all_results = []
            all_results.extend(frame_results)
            all_results.extend(channel_stack_results)
            all_results.extend(time_stack_results)

            for desc, duration, shape in all_results:
                if duration != float("inf"):
                    print(f"{desc}: {duration:.4f}s")

        except Exception as e:
            print(f"Benchmark failed: {e}")


if __name__ == "__main__":
    main()

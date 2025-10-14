#!/usr/bin/env python3
"""
Performance tests for ND2 file loading and frame extraction.
Tests the speed of load_nd2 and get_nd2_* functions.
"""

import time
import logging
from pathlib import Path
from typing import Any

from pyama_core.io.nikon import (
    load_nd2,
    get_nd2_frame,
    get_nd2_channel_stack,
    get_nd2_time_stack,
)


def time_function(func, *args, **kwargs) -> tuple[float, Any]:
    """Time a function call and return (duration, result)."""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    duration = end_time - start_time
    return duration, result


def benchmark_load_nd2(file_path: Path) -> tuple[float, Any, Any]:
    """Benchmark load_nd2 performance - single run."""
    print(f"\nBenchmarking load_nd2 with {file_path}")
    print("-" * 50)

    try:
        duration, (da, metadata) = time_function(load_nd2, file_path)
        print(f"Duration: {duration:.3f}s")
        print(
            f"Loaded {metadata.n_frames} frames, {metadata.n_channels} channels, "
            f"{metadata.n_fovs} FOVs, {metadata.width}×{metadata.height}"
        )
        return duration, da, metadata
    except Exception as e:
        print(f"Failed: {e}")
        return float("inf"), None, None


def benchmark_get_nd2_frame(da, metadata: Any) -> list[tuple[str, float, str]]:
    """Benchmark get_nd2_frame performance - single run per test case."""
    print("\nBenchmarking get_nd2_frame")
    print("-" * 50)

    results = []

    # Test different scenarios
    test_cases = []

    # Basic case: first frame, first channel, first FOV
    if metadata.n_frames > 0 and metadata.n_channels > 0 and metadata.n_fovs > 0:
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
            duration, frame = time_function(get_nd2_frame, da, f=f, c=c, t=t)
            print(f"{desc}: {duration:.4f}s - Shape: {frame.shape}")
            results.append((desc, duration, f"{frame.shape}"))
        except Exception as e:
            print(f"{desc}: Failed - {e}")
            results.append((desc, float("inf"), "Failed"))

    return results


def benchmark_get_nd2_channel_stack(da, metadata: Any) -> list[tuple[str, float, str]]:
    """Benchmark get_nd2_channel_stack performance - single run per test case."""
    print("\nBenchmarking get_nd2_channel_stack")
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
            duration, stack = time_function(get_nd2_channel_stack, da, f=f, t=t)
            print(f"{desc}: {duration:.4f}s - Shape: {stack.shape}")
            results.append((desc, duration, f"{stack.shape}"))
        except Exception as e:
            print(f"{desc}: Failed - {e}")
            results.append((desc, float("inf"), "Failed"))

    return results


def benchmark_get_nd2_time_stack(da, metadata: Any) -> list[tuple[str, float, str]]:
    """Benchmark get_nd2_time_stack performance - single run per test case."""
    print("\nBenchmarking get_nd2_time_stack")
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
            duration, stack = time_function(get_nd2_time_stack, da, f=f, c=c)
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
    print("Starting ND2 performance tests...")

    # Test file path - you can modify this to point to an actual ND2 file
    test_file = Path("/project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2")

    # Check if file exists
    if not test_file.exists():
        print(f"Warning: Test file {test_file} not found.")
        print("Please update the file path to point to a valid ND2 file (.nd2)")
        return

    print(f"Test file: {test_file}")
    print(f"File size: {test_file.stat().st_size / (1024 * 1024):.1f} MB")

    # Benchmark file loading
    load_duration, da, metadata = benchmark_load_nd2(test_file)

    # If loading succeeded, benchmark frame extraction
    if da is not None and metadata is not None:
        try:
            frame_results = benchmark_get_nd2_frame(da, metadata)
            channel_stack_results = benchmark_get_nd2_channel_stack(da, metadata)
            time_stack_results = benchmark_get_nd2_time_stack(da, metadata)

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

"""
Starting ND2 performance tests...
Test file: /project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2
File size: 572384.4 MB

Benchmarking load_nd2 with /project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2
--------------------------------------------------
Duration: 0.210s
Loaded 181 frames, 3 channels, 132 FOVs, 2048×2044

Benchmarking get_nd2_frame
--------------------------------------------------
First frame (f=0, c=0, t=0): 2.2664s - Shape: (2044, 2048)
Second frame (f=0, c=0, t=1): 1.6665s - Shape: (2044, 2048)
Second channel (f=0, c=1, t=0): 0.0224s - Shape: (2044, 2048)
Second FOV (f=1, c=0, t=0): 0.0448s - Shape: (2044, 2048)

Benchmarking get_nd2_channel_stack
--------------------------------------------------
Channel stack (f=0, t=0): 0.0232s - Shape: (3, 2044, 2048)
Channel stack (f=1, t=0): 0.0280s - Shape: (3, 2044, 2048)

Benchmarking get_nd2_time_stack
--------------------------------------------------
Time stack (f=0, c=0): 403.6085s - Shape: (181, 2044, 2048)
Time stack (f=1, c=0): 8.5731s - Shape: (181, 2044, 2048)
Time stack (f=0, c=1): 4.0806s - Shape: (181, 2044, 2048)

=== SUMMARY ===
File loading:      0.210s
First frame (f=0, c=0, t=0): 2.2664s
Second frame (f=0, c=0, t=1): 1.6665s
Second channel (f=0, c=1, t=0): 0.0224s
Second FOV (f=1, c=0, t=0): 0.0448s
Channel stack (f=0, t=0): 0.0232s
Channel stack (f=1, t=0): 0.0280s
Time stack (f=0, c=0): 403.6085s
Time stack (f=1, c=0): 8.5731s
Time stack (f=0, c=1): 4.0806s
"""

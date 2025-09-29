#!/usr/bin/env python3
"""
Performance benchmark for the copying service that's causing 10+ minute delays.
Tests different approaches to copying microscopy data to identify bottlenecks.
"""

import time
import logging
import numpy as np
from pathlib import Path
from typing import Any, Callable

from pyama_core.io import (
    load_microscopy_file,
    get_microscopy_time_stack,
    get_microscopy_frame,
)
from pyama_core.processing.copying.copy import copy_npy
from pyama_core.processing.workflow.services.copying import CopyingService
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext


def time_function(func: Callable, *args, **kwargs) -> tuple[float, Any]:
    """Time a function call and return (duration, result)."""
    start_time = time.perf_counter()
    result = func(*args, **kwargs)
    end_time = time.perf_counter()
    duration = end_time - start_time
    return duration, result


def benchmark_array_copying():
    """Benchmark different array copying approaches."""
    print("\n=== ARRAY COPYING BENCHMARK ===")
    print("-" * 50)

    # Create test arrays
    T, H, W = 100, 1024, 1024  # Typical microscopy dimensions
    source = np.random.randint(0, 65535, (T, H, W), dtype=np.uint16)

    print(f"Test arrays: {source.shape}, dtype: {source.dtype}")
    print(f"Array size: {(source.nbytes / (1024**3)):.2f} GB")

    # Test 1: Original frame-by-frame copying
    print("\n1. Frame-by-frame copying (current implementation):")
    target_copy = np.zeros_like(source)

    def progress_callback(t, T, msg):
        pass  # No progress reporting for benchmark

    duration, _ = time_function(copy_npy, source, target_copy, progress_callback)
    print(f"   Duration: {duration:.3f}s ({duration / T:.4f}s per frame)")

    # Test 2: Direct array assignment (vectorized)
    print("\n2. Direct array assignment (vectorized):")
    target_copy2 = np.zeros_like(source)
    duration, _ = time_function(lambda: np.copyto(target_copy2, source))
    print(f"   Duration: {duration:.3f}s")

    # Test 3: Simple slice assignment
    print("\n3. Simple slice assignment:")
    target_copy3 = np.zeros_like(source)

    def slice_copy():
        target_copy3[:] = source[:]

    duration, _ = time_function(slice_copy)
    print(f"   Duration: {duration:.3f}s")

    # Test 4: Memory mapping approach
    print("\n4. Memory mapping approach:")
    import tempfile
    import os
    from numpy.lib.format import open_memmap

    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        # Create memory map
        memmap_arr = open_memmap(
            tmp_path, mode="w+", dtype=np.uint16, shape=source.shape
        )

        def copy_to_memmap():
            np.copyto(memmap_arr, source)

        duration, _ = time_function(copy_to_memmap)
        print(f"   Duration: {duration:.3f}s")

        # Clean up
        try:
            memmap_arr.flush()
            del memmap_arr
        except Exception:
            pass
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def benchmark_microscopy_operations(file_path: Path):
    """Benchmark microscopy file operations."""
    print("\n=== MICROSCOPY OPERATIONS BENCHMARK ===")
    print("-" * 50)

    # Load file once
    print(f"Loading microscopy file: {file_path}")
    load_duration, (img, metadata) = time_function(load_microscopy_file, file_path)
    print(f"File loading: {load_duration:.3f}s")
    print(
        f"Metadata: {metadata.n_frames} frames, {metadata.n_channels} channels, "
        f"{metadata.width}×{metadata.height}"
    )

    if metadata.n_frames == 0 or metadata.n_channels == 0:
        print("No frames or channels to test!")
        return

    # Test time stack extraction
    print("\n1. Time stack extraction (get_microscopy_time_stack):")
    fov, ch = 0, 0  # First FOV, first channel

    duration, time_stack = time_function(get_microscopy_time_stack, img, fov, ch)
    print(f"   Duration: {duration:.3f}s")
    print(f"   Stack shape: {time_stack.shape}")

    # Test frame-by-frame extraction
    print("\n2. Frame-by-frame extraction:")
    frame_durations = []
    n_frames_to_test = min(10, metadata.n_frames)  # Test first 10 frames

    for t in range(n_frames_to_test):
        duration, frame = time_function(get_microscopy_frame, img, fov, ch, t)
        frame_durations.append(duration)
        if t == 0:
            print(f"   Frame 0: {duration:.4f}s, shape: {frame.shape}")

    avg_frame_duration = sum(frame_durations) / len(frame_durations)
    print(f"   Average per frame: {avg_frame_duration:.4f}s")
    print(f"   Total for {n_frames_to_test} frames: {sum(frame_durations):.3f}s")

    # Compare with time stack approach
    time_stack_duration = duration
    estimated_frame_by_frame = avg_frame_duration * metadata.n_frames
    print("\n3. Performance comparison:")
    print(f"   Time stack approach: {time_stack_duration:.3f}s")
    print(f"   Frame-by-frame (estimated): {estimated_frame_by_frame:.3f}s")
    print(f"   Speedup factor: {estimated_frame_by_frame / time_stack_duration:.1f}x")


def benchmark_copy_service_workflow(file_path: Path, output_dir: Path):
    """Benchmark the actual copying service workflow."""
    print("\n=== COPYING SERVICE WORKFLOW BENCHMARK ===")
    print("-" * 50)

    # Setup like in test_workflow.py
    print(f"Test file: {file_path}")
    print(f"Output dir: {output_dir}")

    # Load metadata
    _, metadata = load_microscopy_file(file_path)

    # Setup context like in test_workflow.py
    context = ProcessingContext(
        output_dir=output_dir,
        channels=Channels(pc=0, fl=[1, 2]),  # Test multiple channels
        params={},
    )

    # Create copy service
    copy_service = CopyingService()

    # Test single FOV processing
    fov = 0
    print(f"\nTesting FOV {fov} processing:")

    duration, _ = time_function(
        copy_service.process_fov, metadata, context, output_dir, fov
    )
    print(f"   Duration: {duration:.3f}s")

    # Show what was created
    fov_dir = output_dir / f"fov_{fov:03d}"
    if fov_dir.exists():
        files = list(fov_dir.glob("*.npy"))
        total_size = sum(f.stat().st_size for f in files)
        print(
            f"   Created {len(files)} files, total size: {total_size / (1024 * 1024):.1f} MB"
        )

        # List the files
        for f in files:
            print(f"     {f.name}")


def benchmark_optimized_approaches(file_path: Path, output_dir: Path):
    """Test optimized copying approaches."""
    print("\n=== OPTIMIZED COPYING APPROACHES ===")
    print("-" * 50)

    # Load file once
    _, (img, metadata) = time_function(load_microscopy_file, file_path)

    fov = 0
    channels_to_test = [0, 1]  # Test first two channels

    print(f"Testing optimized approaches for FOV {fov}:")

    for ch in channels_to_test:
        print(f"\nChannel {ch}:")

        # Method 1: Current approach (time stack + copy_npy)
        print("  1. Current approach (time stack + frame-by-frame copy):")
        start_time = time.perf_counter()

        # Get time stack
        stack_duration, time_stack = time_function(
            get_microscopy_time_stack, img, fov, ch
        )
        print(f"     Time stack extraction: {stack_duration:.3f}s")

        # Create output array
        T, H, W = time_stack.shape
        output_array = np.zeros((T, H, W), dtype=np.uint16)

        # Copy using current method
        def dummy_progress(t, T, msg):
            pass

        copy_duration, _ = time_function(
            copy_npy, time_stack, output_array, dummy_progress
        )
        print(f"     Frame-by-frame copy: {copy_duration:.3f}s")

        total_current = time.perf_counter() - start_time
        print(f"     Total: {total_current:.3f}s")

        # Method 2: Optimized approach (direct array copy)
        print("  2. Optimized approach (direct array copy):")
        start_time = time.perf_counter()

        # Get time stack
        stack_duration2, time_stack2 = time_function(
            get_microscopy_time_stack, img, fov, ch
        )

        # Direct copy to memory-mapped array
        output_path2 = output_dir / f"test_ch_{ch}_optimized.npy"
        memmap_array = np.memmap(
            output_path2, mode="w+", dtype=np.uint16, shape=time_stack2.shape
        )

        direct_copy_duration, _ = time_function(np.copyto, memmap_array, time_stack2)
        print(f"     Direct copy: {direct_copy_duration:.3f}s")

        memmap_array.flush()
        del memmap_array

        total_optimized = time.perf_counter() - start_time
        print(f"     Total: {total_optimized:.3f}s")

        speedup = total_current / total_optimized if total_optimized > 0 else 1
        print(f"     Speedup: {speedup:.1f}x")


def main():
    """Main benchmark function."""
    logging.basicConfig(level=logging.INFO)
    print("Starting copying performance benchmark...")

    # Use the same test file as in test_workflow.py
    test_file = Path("/project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2")
    output_dir = Path("/tmp/pyama_copying_benchmark")

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Check if test file exists
    if not test_file.exists():
        print(f"Test file {test_file} not found!")
        print("Please update the file path to point to a valid microscopy file.")
        return

    print(f"Test file size: {test_file.stat().st_size / (1024 * 1024):.1f} MB")

    # Run benchmarks
    benchmark_array_copying()
    benchmark_microscopy_operations(test_file)
    benchmark_copy_service_workflow(test_file, output_dir)
    benchmark_optimized_approaches(test_file, output_dir)

    print("\n=== RECOMMENDATIONS ===")
    print("1. Replace frame-by-frame copying with direct array operations")
    print("2. Use memory mapping for large arrays")
    print("3. Load microscopy file once and reuse across channels")
    print("4. Consider parallel processing for multiple FOVs/channels")


if __name__ == "__main__":
    main()

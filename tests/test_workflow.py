#!/usr/bin/env python3
"""
Test script for PyAMA complete workflow.

This script tests the full processing workflow from ND2 file to results generation.
It processes microscopy data through all steps: segmentation, background estimation,
tracking, and feature extraction.

Usage:
    python test_workflow.py [--nd2-path PATH] [--output-dir PATH]
"""

import argparse
import logging
from pathlib import Path

from pyama_core.io import load_microscopy_file
from pyama_core.processing.workflow.run import run_complete_workflow
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.types.processing import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)


def setup_logging():
    """Configure logging for workflow execution."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    print("✓ Logging configured")


def create_processing_context(microscopy_path, output_dir, metadata):
    """Create a ProcessingContext with appropriate channel and feature selections.
    
    Args:
        microscopy_path: Path to ND2 file
        output_dir: Directory for output files
        metadata: MicroscopyMetadata from loaded file
    
    Returns:
        ProcessingContext configured for processing
    """
    print("\n" + "="*60)
    print("Setting up processing context")
    print("="*60)
    
    # Get available features
    print("Discovering available features...")
    phase_features = list_phase_features()
    fluorescence_features = list_fluorescence_features()
    
    print(f"   Phase contrast features: {phase_features}")
    print(f"   Fluorescence features: {fluorescence_features}")
    
    # Configure channels based on what's available
    n_channels = metadata.n_channels
    
    # Phase contrast (channel 0)
    pc_selection = ChannelSelection(channel=0, features=phase_features)
    
    # Fluorescence channels (1, 2, ...)
    fl_selections = []
    for ch in range(1, min(n_channels, 3)):  # Process up to 2 fluorescence channels
        fl_selections.append(ChannelSelection(channel=ch, features=fluorescence_features))
    
    # Create context
    context = ProcessingContext(
        output_dir=output_dir,
        channels=Channels(pc=pc_selection, fl=fl_selections),
        params={"background_weight": 0.0},
    )
    
    print(f"\n✓ Context created:")
    print(f"   Phase contrast: channel {pc_selection.channel}, "
          f"features {pc_selection.features}")
    print(f"   Fluorescence channels: {[fl.channel for fl in fl_selections]}")
    for fl in fl_selections:
        print(f"     Channel {fl.channel}: {fl.features}")
    
    return context


def run_workflow(context, metadata, fov_start=0, fov_end=None, batch_size=2, n_workers=2):
    """Execute the complete processing workflow.
    
    Args:
        context: ProcessingContext with channel configuration
        metadata: MicroscopyMetadata from loaded file
        fov_start: First FOV to process (default: 0)
        fov_end: Last FOV to process (default: min(1, n_fovs-1))
        batch_size: Number of FOVs to process in each batch
        n_workers: Number of parallel workers
    
    Returns:
        bool: True if workflow completed successfully
    """
    print("\n" + "="*60)
    print("Running workflow")
    print("="*60)
    
    if fov_end is None:
        fov_end = min(1, metadata.n_fovs - 1)
    
    print(f"Configuration:")
    print(f"   FOV range: {fov_start} to {fov_end}")
    print(f"   Batch size: {batch_size}")
    print(f"   Workers: {n_workers}")
    print(f"\nStarting workflow execution...")
    print(f"   (This may take several minutes depending on data size)")
    
    try:
        success = run_complete_workflow(
            metadata=metadata,
            context=context,
            fov_start=fov_start,
            fov_end=fov_end,
            batch_size=batch_size,
            n_workers=n_workers,
        )
        
        if success:
            print("\n✓ Workflow completed successfully!")
        else:
            print("\n❌ Workflow completed with errors")
        
        return success
        
    except Exception as e:
        print(f"\n❌ Workflow execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def inspect_results(context, output_dir):
    """Inspect and display workflow results.
    
    Args:
        context: ProcessingContext after workflow execution
        output_dir: Output directory path
    """
    print("\n" + "="*60)
    print("Inspecting results")
    print("="*60)
    
    # Show context results
    print("Processing results:")
    if context.results:
        print(f"   FOVs processed: {list(context.results.keys())}")
        for fov_id, result in context.results.items():
            print(f"\n   FOV {fov_id}:")
            if result.pc:
                ch, path = result.pc
                print(f"     Phase contrast: channel {ch} -> {path.name}")
            if result.fl:
                print(f"     Fluorescence: {len(result.fl)} channel(s)")
                for ch, path in result.fl:
                    print(f"       Channel {ch}: {path.name}")
            if result.fl_background:
                print(f"     Background: {len(result.fl_background)} channel(s)")
                for ch, path in result.fl_background:
                    print(f"       Channel {ch}: {path.name}")
            if result.seg:
                ch, path = result.seg
                print(f"     Segmentation: channel {ch} -> {path.name}")
            if result.seg_labeled:
                ch, path = result.seg_labeled
                print(f"     Tracked segmentation: channel {ch} -> {path.name}")
            if result.traces:
                print(f"     Traces: {result.traces.name}")
    else:
        print("   No results found")
    
    # List output files
    print(f"\nOutput directory contents ({output_dir}):")
    if output_dir.exists():
        files = sorted(output_dir.rglob("*"))
        file_count = 0
        total_size_mb = 0
        
        for file_path in files:
            if file_path.is_file():
                rel_path = file_path.relative_to(output_dir)
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"   {rel_path} ({size_mb:.2f} MB)")
                file_count += 1
                total_size_mb += size_mb
        
        print(f"\n   Total: {file_count} files, {total_size_mb:.2f} MB")
    else:
        print("   Directory does not exist")
    
    # Check for processing results YAML
    yaml_path = output_dir / "processing_results.yaml"
    if yaml_path.exists():
        print(f"\n✓ Processing results YAML found: {yaml_path}")
        
        try:
            from pyama_core.io.results_yaml import load_processing_results_yaml
            results = load_processing_results_yaml(yaml_path)
            
            print("   YAML contents:")
            if "channels" in results:
                ch = results["channels"]
                if "pc" in ch:
                    print(f"     Phase contrast: {ch['pc']}")
                if "fl" in ch:
                    print(f"     Fluorescence: {ch['fl']}")
            
            if "results" in results:
                fovs = list(results["results"].keys())
                print(f"     FOVs: {fovs}")
                for fov_id in fovs:
                    fov_data = results["results"][fov_id]
                    print(f"       FOV {fov_id}: {list(fov_data.keys())}")
        except Exception as e:
            print(f"   ❌ Error loading YAML: {e}")


def main():
    """Run the complete workflow test."""
    parser = argparse.ArgumentParser(
        description="Test PyAMA complete workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--nd2-path",
        type=Path,
        default=Path("D:/250129_HuH7.nd2"),
        help="Path to ND2 microscopy file",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: same as ND2 file directory)",
    )
    parser.add_argument(
        "--fov-start",
        type=int,
        default=0,
        help="First FOV to process (default: 0)",
    )
    parser.add_argument(
        "--fov-end",
        type=int,
        default=None,
        help="Last FOV to process (default: 1)",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
        help="Batch size for processing (default: 2)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=2,
        help="Number of parallel workers (default: 2)",
    )
    args = parser.parse_args()
    
    print("="*60)
    print("PyAMA Workflow Testing")
    print("="*60)
    print(f"ND2 file: {args.nd2_path}")
    
    # Setup
    setup_logging()
    
    # Determine output directory
    if args.output_dir is None:
        output_dir = args.nd2_path.parent
    else:
        output_dir = args.output_dir
    
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output directory: {output_dir}\n")
    
    # Load microscopy file
    print("Loading microscopy file...")
    if not args.nd2_path.exists():
        print(f"❌ File not found: {args.nd2_path}")
        print("   Please update --nd2-path to point to your test file")
        return
    
    try:
        img, metadata = load_microscopy_file(args.nd2_path)
        print(f"✓ Loaded successfully")
        print(f"   Channels: {metadata.n_channels}")
        print(f"   Channel names: {metadata.channel_names}")
        print(f"   Timepoints: {metadata.n_frames}")
        print(f"   FOVs: {metadata.n_fovs}")
        print(f"   Image shape: {img.shape}")
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return
    
    # Create processing context
    context = create_processing_context(args.nd2_path, output_dir, metadata)
    
    # Run workflow
    success = run_workflow(
        context, metadata,
        fov_start=args.fov_start,
        fov_end=args.fov_end,
        batch_size=args.batch_size,
        n_workers=args.workers,
    )
    
    # Inspect results
    inspect_results(context, output_dir)
    
    # Summary
    print(f"\n{'='*60}")
    if success:
        print("✓ Workflow testing completed successfully!")
        print("✓ All processing steps completed")
        print("✓ Results files generated")
    else:
        print("⚠ Workflow testing completed with issues")
        print("⚠ Some processing steps may have failed")
    print(f"{'='*60}")
    print(f"Output directory: {output_dir}")
    print(f"Microscopy file: {args.nd2_path}")


if __name__ == "__main__":
    main()

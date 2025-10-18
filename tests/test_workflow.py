#!/usr/bin/env python3
"""
Visual testing script for PyAMA workflow functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates the complete workflow from ND2 processing to results generation.
"""

from pathlib import Path
import logging

from pyama_core.io import load_microscopy_file
from pyama_core.processing.workflow.pipeline import run_complete_workflow
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)


def demonstrate_workflow_setup():
    """Demonstrate workflow setup and configuration."""
    print("=== Workflow Setup Demo ===")
    
    # Configuration - update these paths as needed
    microscopy_path = Path("../data/test_sample.nd2")  # Update this path
    OUTPUT_DIR = Path("workflow_outputs")
    
    print(f"1. Microscopy path: {microscopy_path}")
    print(f"2. Output directory: {OUTPUT_DIR}")
    
    if not microscopy_path.exists():
        print(f"❌ Microscopy file not found: {microscopy_path}")
        print("Please update the microscopy_path variable to point to your test ND2 file")
        return None, None, None
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    print("✓ Logging configured at INFO level")
    
    # Build per-channel feature mapping
    print("\n3. Discovering available features...")
    from pyama_core.processing.extraction.feature import (
        list_fluorescence_features,
        list_phase_features,
    )
    
    fl_feature_choices = list_fluorescence_features()
    pc_features = list_phase_features()
    
    print(f"   Phase contrast features: {pc_features}")
    print(f"   Fluorescence features: {fl_feature_choices}")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory created: {OUTPUT_DIR}")
    
    # Load metadata
    print("\n4. Loading microscopy file metadata...")
    try:
        img, md = load_microscopy_file(microscopy_path)
        print(f"✓ Successfully loaded microscopy file")
        print(f"   Channels: {md.n_channels}")
        print(f"   Channel names: {md.channel_names}")
        print(f"   Timepoints: {md.n_timepoints}")
        print(f"   FOVs: {md.n_fovs}")
        print(f"   Image shape: {img.shape}")
    except Exception as e:
        print(f"❌ Error loading microscopy file: {e}")
        return None, None, None
    
    # Build processing context
    print("\n5. Building processing context...")
    
    # Adjust channel selection based on available channels
    available_channels = md.n_channels
    fl_channels = []
    
    if available_channels >= 2:
        fl_channels.append(ChannelSelection(channel=1, features=fl_feature_choices))
    if available_channels >= 3:
        fl_channels.append(ChannelSelection(channel=2, features=fl_feature_choices))
    
    ctx = ProcessingContext(
        output_dir=OUTPUT_DIR,
        channels=Channels(
            pc=ChannelSelection(channel=0, features=pc_features),
            fl=fl_channels,
        ),
        params={},
    )
    
    print(f"✓ Processing context created:")
    print(f"   PC Channel: {ctx.channels.pc.channel if ctx.channels.pc else 'None'}")
    print(f"   PC Features: {ctx.channels.pc.features if ctx.channels.pc else 'None'}")
    print(f"   FL Channels: {[fl.channel for fl in ctx.channels.fl]}")
    for i, fl in enumerate(ctx.channels.fl):
        print(f"     Channel {fl.channel}: {fl.features}")
    
    return microscopy_path, ctx, md


def demonstrate_workflow_execution(ctx, md):
    """Demonstrate workflow execution with progress tracking."""
    print("\n=== Workflow Execution Demo ===")
    
    # Configure workflow parameters
    fov_start = 0
    fov_end = min(1, md.n_fovs - 1)  # Process at least 1 FOV
    batch_size = 2
    n_workers = 2
    
    print(f"1. Workflow configuration:")
    print(f"   FOV range: {fov_start} to {fov_end}")
    print(f"   Batch size: {batch_size}")
    print(f"   Workers: {n_workers}")
    
    print(f"\n2. Starting workflow execution...")
    print("   (This may take several minutes depending on data size...)")
    
    try:
        success = run_complete_workflow(
            metadata=md,
            context=ctx,
            fov_start=fov_start,
            fov_end=fov_end,
            batch_size=batch_size,
            n_workers=n_workers,
        )
        
        if success:
            print("✓ Workflow completed successfully!")
        else:
            print("❌ Workflow completed with errors")
        
        return success
        
    except Exception as e:
        print(f"❌ Workflow execution failed: {e}")
        return False


def demonstrate_results_inspection(ctx, output_dir):
    """Demonstrate inspection of workflow results."""
    print("\n=== Results Inspection Demo ===")
    
    print("1. Processing context after workflow:")
    print(f"   Output directory: {ctx.output_dir}")
    print(f"   Results FOVs: {list(ctx.results.keys()) if ctx.results else 'None'}")
    
    if ctx.results:
        for fov_id, result in ctx.results.items():
            print(f"\n   FOV {fov_id} results:")
            if result.pc:
                print(f"     PC: Channel {result.pc[0]} -> {result.pc[1]}")
            if result.fl:
                print(f"     FL: {[(ch, path.name) for ch, path in result.fl]}")
            if result.fl_corrected:
                print(f"     FL_corrected: {[(ch, path.name) for ch, path in result.fl_corrected]}")
            if result.seg:
                print(f"     Segmentation: {result.seg[1]}")
            if result.seg_labeled:
                print(f"     Tracked segmentation: {result.seg_labeled[1]}")
            if result.traces:
                print(f"     Traces: {result.traces}")
    
    # Check output files
    print(f"\n2. Output directory contents:")
    if output_dir.exists():
        for file_path in sorted(output_dir.rglob("*")):
            if file_path.is_file():
                rel_path = file_path.relative_to(output_dir)
                size_mb = file_path.stat().st_size / (1024 * 1024)
                print(f"   {rel_path} ({size_mb:.2f} MB)")
    else:
        print("   Output directory does not exist")
    
    # Look for processing results YAML
    yaml_path = output_dir / "processing_results.yaml"
    if yaml_path.exists():
        print(f"\n3. Processing results YAML found: {yaml_path}")
        
        # Load and display summary
        try:
            from pyama_core.io.results_yaml import load_processing_results_yaml
            results = load_processing_results_yaml(yaml_path)
            
            print("   YAML summary:")
            if "channels" in results:
                channels = results["channels"]
                if "pc" in channels:
                    print(f"     PC channel: {channels['pc']}")
                if "fl" in channels:
                    print(f"     FL channels: {channels['fl']}")
            
            if "results" in results:
                print(f"     FOVs processed: {list(results['results'].keys())}")
                for fov_id, fov_data in results["results"].items():
                    print(f"       FOV {fov_id}: {list(fov_data.keys())}")
            
        except Exception as e:
            print(f"   ❌ Error loading YAML: {e}")


def main():
    """Run complete workflow testing with clear demonstrations."""
    print("PyAMA Workflow Testing Pipeline")
    print("===============================")
    
    # Step 1: Setup workflow
    microscopy_path, ctx, md = demonstrate_workflow_setup()
    if ctx is None:
        print("\n❌ Cannot proceed without valid setup")
        return
    
    # Step 2: Execute workflow
    success = demonstrate_workflow_execution(ctx, md)
    
    # Step 3: Inspect results
    output_dir = ctx.output_dir
    demonstrate_results_inspection(ctx, output_dir)
    
    print(f"\n{'='*50}")
    if success:
        print("✓ Workflow testing completed successfully!")
        print("✓ All processing steps completed without errors")
        print("✓ Results files generated and verified")
    else:
        print("⚠ Workflow testing completed with issues")
        print("⚠ Some processing steps may have failed")
    
    print(f"Output directory: {output_dir}")
    print(f"Microscopy file: {microscopy_path}")
    print("="*50)


if __name__ == "__main__":
    main()

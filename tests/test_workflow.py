#!/usr/bin/env python3
"""
Visual testing script for PyAMA workflow functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates the complete workflow from ND2 processing to results generation.
"""

import logging
from pathlib import Path

from pyama_core.io import load_microscopy_file
from pyama_core.processing.workflow.run import run_complete_workflow
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)


def demonstrate_workflow_setup():
    """Demonstrate workflow setup and configuration."""
    print("=== Workflow Setup Demo ===")

    # Configuration - update these paths as needed
    microscopy_path = Path("D:/250129_HuH7.nd2")  # Update this path
    output_dir = Path("D:/250129_HuH7")

    print(f"1. Microscopy path: {microscopy_path}")
    print(f"2. Output directory: {output_dir}")

    if not microscopy_path.exists():
        print(f"❌ Microscopy file not found: {microscopy_path}")
        print(
            "Please update the microscopy_path variable to point to your test ND2 file"
        )
        return None, None, None

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    print("✓ Logging configured at INFO level")

    # Build per-channel feature mapping
    print("\n3. Discovering available features...")
    from pyama_core.processing.extraction.features import (
        list_fluorescence_features,
        list_phase_features,
    )

    fl_feature_choices = list_fluorescence_features()
    pc_features = list_phase_features()

    print(f"   Phase contrast features: {pc_features}")
    print(f"   Fluorescence features: {fl_feature_choices}")

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"✓ Output directory created: {output_dir}")

    # Load metadata
    print("\n4. Loading microscopy file metadata...")
    try:
        img, md = load_microscopy_file(microscopy_path)
        print("✓ Successfully loaded microscopy file")
        print(f"   Channels: {md.n_channels}")
        print(f"   Channel names: {md.channel_names}")
        print(f"   Timepoints: {md.n_frames}")
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
        fl_channels.append({"channel": 1, "features": fl_feature_choices})
    if available_channels >= 3:
        fl_channels.append({"channel": 2, "features": fl_feature_choices})

    from pyama_core.processing.workflow.services.types import (
        get_fl_channels,
        get_pc_channel,
        get_pc_features,
    )

    ctx: ProcessingContext = {
        "output_dir": str(output_dir),
        "channels": {
            "pc": {"channel": 0, "features": pc_features},
            "fl": fl_channels,
        },
        "params": {"background_weight": 0.0},
    }

    print("✓ Processing context created:")
    ctx_channels = ctx.get("channels", {})
    pc_channel = get_pc_channel(ctx_channels) if ctx_channels else None
    pc_features_list = get_pc_features(ctx_channels) if ctx_channels else []
    fl_channels_list = get_fl_channels(ctx_channels) if ctx_channels else []
    print(f"   PC Channel: {pc_channel}")
    print(f"   PC Features: {pc_features_list}")
    print(f"   FL Channels: {fl_channels_list}")
    if ctx_channels:
        for selection in ctx_channels.get("fl", []):
            print(f"     Channel {selection.get('channel')}: {selection.get('features')}")

    return microscopy_path, ctx, md


def demonstrate_workflow_execution(ctx, md):
    """Demonstrate workflow execution with progress tracking."""
    print("\n=== Workflow Execution Demo ===")

    # Configure workflow parameters
    fov_start = 0
    fov_end = min(1, md.n_fovs - 1)  # Process at least 1 FOV
    batch_size = 2
    n_workers = 2

    print("1. Workflow configuration:")
    print(f"   FOV range: {fov_start} to {fov_end}")
    print(f"   Batch size: {batch_size}")
    print(f"   Workers: {n_workers}")

    print("\n2. Starting workflow execution...")
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
    print(f"   Output directory: {ctx.get('output_dir')}")
    print(f"   Results FOVs: {list(ctx.get('results', {}).keys()) if ctx.get('results') else 'None'}")

    ctx_results = ctx.get("results")
    if ctx_results:
        for fov_id, result in ctx_results.items():
            print(f"\n   FOV {fov_id} results:")
            result_pc = result.get("pc")
            if result_pc:
                print(f"     PC: Channel {result_pc[0]} -> {result_pc[1]}")
            result_fl = result.get("fl")
            if result_fl:
                print(f"     FL: {[(ch, Path(path).name) for ch, path in result_fl]}")
            result_fl_corrected = result.get("fl_background")
            if result_fl_corrected:
                print(
                    f"     FL_corrected: {[(ch, Path(path).name) for ch, path in result_fl_corrected]}"
                )
            result_seg = result.get("seg")
            if result_seg:
                print(f"     Segmentation: {result_seg[1]}")
            result_seg_labeled = result.get("seg_labeled")
            if result_seg_labeled:
                print(f"     Tracked segmentation: {result_seg_labeled[1]}")
            result_traces = result.get("traces")
            if result_traces:
                print(f"     Traces: {result_traces}")

    # Check output files
    print("\n2. Output directory contents:")
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
    output_dir = ctx.get("output_dir")
    demonstrate_results_inspection(ctx, output_dir)

    print(f"\n{'=' * 50}")
    if success:
        print("✓ Workflow testing completed successfully!")
        print("✓ All processing steps completed without errors")
        print("✓ Results files generated and verified")
    else:
        print("⚠ Workflow testing completed with issues")
        print("⚠ Some processing steps may have failed")

    print(f"Output directory: {output_dir}")
    print(f"Microscopy file: {microscopy_path}")
    print("=" * 50)


if __name__ == "__main__":
    main()

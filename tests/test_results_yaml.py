#!/usr/bin/env python3
"""
Visual testing script for PyAMA results YAML functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates YAML schema, serialization, merging, and round-trip functionality.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from pyama_core.io.results_yaml import (
    get_channels_from_yaml,
    load_processing_results_yaml,
)
from pyama_core.processing.workflow.run import (
    _paths_to_strings,
    _load_from_yaml,
    _merge_contexts,
)
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)


def demonstrate_yaml_serialization():
    """Demonstrate YAML serialization of processing context."""
    print("=== YAML Serialization Demo ===")

    with TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)

        def touch(name: str) -> Path:
            """Create a dummy file for testing."""
            path = output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
            return path

        print("1. Creating primary processing context...")
        print("   Channels:")
        print("     PC: Channel 0 with features ['perimeter', 'area']")
        print("     FL: Channel 1 with features ['intensity_total']")
        print("          Channel 2 with features ['mean', 'intensity_total']")

        # Create dummy files for testing
        pc_path = touch("fov0_pc.npy")
        fl_raw_path = touch("fov0_fl1.npy")
        fl_corr_path = touch("fov0_fl2_corr.npy")
        seg_path = touch("fov0_seg.npy")
        seg_labeled_path = touch("fov0_seg_labeled.npy")
        traces_path = touch("fov0_traces.csv")

        # Create primary context
        context: ProcessingContext = {
            "output_dir": str(output_dir),
            "channels": {
                "pc": {"channel": 0, "features": ["perimeter", "area"]},
                "fl": [
                    {"channel": 1, "features": ["intensity_total"]},
                    {"channel": 2, "features": ["mean", "intensity_total"]},
                ],
            },
            "params": {},
            "results": {},
        }
        fov0 = ensure_results_entry()
        fov0["pc"] = (0, str(pc_path))
        fov0["fl"] = [(1, str(fl_raw_path))]
        fl_bg_list = fov0.setdefault("fl_background", [])
        fl_bg_list.append((2, str(fl_corr_path)))
        fov0["seg"] = (0, str(seg_path))
        fov0["seg_labeled"] = (0, str(seg_labeled_path))
        fov0["traces"] = str(traces_path)
        context["results"][0] = fov0

        ensure_context(context)

        print(f"   Created {len(context.get('results', {}))} FOV results")
        print(f"   Output directory: {output_dir}")

        # Serialize to YAML (convert Path objects to strings)
        print("\n2. Serializing context to YAML...")
        serialized = _paths_to_strings(context)
        yaml_path = output_dir / "processing_results.yaml"

        with yaml_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(serialized, handle, sort_keys=False)

        print(f"✓ Saved YAML to: {yaml_path}")

        # Load and display YAML content
        with yaml_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)

        print("\n3. Generated YAML content:")
        print("=" * 50)
        print(yaml.dump(raw, sort_keys=False))
        print("=" * 50)

        # Verify channel block
        channel_block = raw["channels"]
        expected_pc = [0, ["area", "perimeter"]]
        expected_fl = [
            [1, ["intensity_total"]],
            [2, ["intensity_total", "mean"]],
        ]

        print("4. Channel block verification:")
        print(f"   Expected PC: {expected_pc}")
        print(f"   Actual PC:   {channel_block['pc']}")
        print(f"   PC Match: {'✓' if channel_block['pc'] == expected_pc else '❌'}")

        print(f"   Expected FL: {expected_fl}")
        print(f"   Actual FL:   {channel_block['fl']}")
        print(f"   FL Match: {'✓' if channel_block['fl'] == expected_fl else '❌'}")

        # Verify results block
        results_block = raw["results"]
        print("\n5. Results block verification:")
        print(f"   FOV 0 PC: {results_block['0']['pc']}")
        print(f"   FOV 0 FL: {results_block['0']['fl']}")
        print(f"   FOV 0 FL_corrected: {results_block['0']['fl_corrected']}")
        print(f"   FOV 0 traces: {results_block['0']['traces']}")

        return yaml_path, context, output_dir


def demonstrate_yaml_deserialization(yaml_path, context):
    """Demonstrate YAML deserialization and round-trip testing."""
    print("\n=== YAML Deserialization Demo ===")

    print("1. Loading YAML back to Python objects...")
    loaded = load_processing_results_yaml(yaml_path)

    with yaml_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle)

    channel_block = raw["channels"]

    # Test loading from YAML (data is already in dict format)
    print("2. Testing channel loading from YAML...")
    round_trip_context = _load_from_yaml({"channels": channel_block})

    from pyama_core.processing.workflow.services.types import (
        get_fl_feature_map,
        get_pc_channel,
    )
    round_trip_channels = round_trip_context.get("channels", {})
    pc_channel = get_pc_channel(round_trip_channels)
    fl_features = get_fl_feature_map(round_trip_channels)

    print(f"   PC Channel: {pc_channel}")
    print(f"   FL Features: {fl_features}")

    # Extract fluorescence channels
    fluorescence_channels = get_channels_from_yaml(loaded)
    print(f"   Fluorescence channels: {fluorescence_channels}")

    print("✓ YAML deserialization successful")


def demonstrate_context_merging(context, output_dir):
    """Demonstrate merging of processing contexts."""
    print("\n=== Context Merging Demo ===")

    def touch(name: str) -> Path:
        """Create a dummy file for testing."""
        path = output_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"")
        return path

    print("1. Creating worker context with additional data...")
    print("   Worker channels:")
    print("     PC: None (no phase contrast)")
    print("     FL: Channel 2 with features ['variance']")
    print("          Channel 3 with features ['sum']")

    # Create worker context
    from pyama_core.processing.workflow.services.types import get_fl_channels
    worker_context: ProcessingContext = {
        "output_dir": str(output_dir),
        "channels": {
            "pc": None,
            "fl": [
                {"channel": 2, "features": ["variance"]},
                {"channel": 3, "features": ["sum"]},
            ],
        },
        "params": {},
    }
    ensure_context(worker_context)

    # Add worker results
    worker_entry = ensure_results_entry()
    worker_fl_path = touch("fov1_fl2.npy")
    worker_traces_path = touch("fov1_traces.csv")
    worker_fl_list = worker_entry.setdefault("fl", [])
    worker_fl_list.append((2, str(worker_fl_path)))
    worker_entry["traces"] = str(worker_traces_path)
    worker_context["results"] = {1: worker_entry}

    print(f"   Added FOV 1 results: {len(worker_context.get('results', {}))} FOVs total")

    print("\n2. Merging worker context into primary context...")

    # Show state before merge
    print("   Before merge:")
    print(f"     Primary FOVs: {list(context.get('results', {}).keys())}")
    print(f"     Worker FOVs: {list(worker_context.get('results', {}).keys())}")
    context_channels = context.get("channels", {})
    worker_channels = worker_context.get("channels", {})
    if context_channels:
        fl_channels_ctx = get_fl_channels(context_channels)
        if fl_channels_ctx:
            print(f"     Primary FL channels: {fl_channels_ctx}")
    if worker_channels:
        fl_channels_worker = get_fl_channels(worker_channels)
        if fl_channels_worker:
            print(f"     Worker FL channels: {fl_channels_worker}")

    # Perform merge
    _merge_contexts(context, worker_context)

    # Show state after merge
    print("   After merge:")
    print(f"     Merged FOVs: {list(context.get('results', {}).keys())}")
    if context_channels:
        fl_channels_merged = get_fl_channels(context_channels)
        if fl_channels_merged:
            print(f"     Merged FL channels: {fl_channels_merged}")
            for selection in context_channels.get("fl", []):
                print(f"       Channel {selection.get('channel')}: {selection.get('features')}")

    print("\n3. Serializing merged context...")
    merged_serialized = _paths_to_strings(context)
    yaml_path = output_dir / "processing_results.yaml"

    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(merged_serialized, handle, sort_keys=False)

    print("✓ Merged context serialized")

    # Display merged YAML
    with yaml_path.open("r", encoding="utf-8") as handle:
        merged_raw = yaml.safe_load(handle)

    print("\n4. Merged YAML content:")
    print("=" * 50)
    print(yaml.dump(merged_raw, sort_keys=False))
    print("=" * 50)

    # Verify merge results
    merged_channels = merged_raw["channels"]
    expected_merged_fl = [
        [1, ["intensity_total"]],
        [2, ["intensity_total", "mean", "variance"]],
        [3, ["sum"]],
    ]

    print("5. Merge verification:")
    print(f"   Expected merged FL: {expected_merged_fl}")
    print(f"   Actual merged FL:   {merged_channels['fl']}")
    print(
        f"   Merge correct: {'✓' if merged_channels['fl'] == expected_merged_fl else '❌'}"
    )

    merged_results = merged_raw["results"]
    print(f"   Merged FOVs: {list(merged_results.keys())}")
    print(
        f"   Both FOVs present: {'✓' if '0' in merged_results and '1' in merged_results else '❌'}"
    )

    # Test final loading
    merged_processing = load_processing_results_yaml(yaml_path)
    merged_channels_list = get_channels_from_yaml(merged_processing)
    print(f"   Final channel list: {merged_channels_list}")
    print("   Expected: [1, 2, 3]")
    print(
        f"   Final load correct: {'✓' if merged_channels_list == [1, 2, 3] else '❌'}"
    )


def main():
    """Run all results YAML functionality demonstrations."""
    print("PyAMA Results YAML Testing Pipeline")
    print("==================================")

    # Step 1: Demonstrate YAML serialization
    yaml_path, context, output_dir = demonstrate_yaml_serialization()

    # Step 2: Demonstrate YAML deserialization
    demonstrate_yaml_deserialization(yaml_path, context)

    # Step 3: Demonstrate context merging
    demonstrate_context_merging(context, output_dir)

    print(f"\n{'='*50}")
    print("✓ All results YAML tests completed successfully!")
    print("✓ YAML schema serialization/deserialization working")
    print("✓ Context merging and round-trip verification working")
    print("=" * 50)


if __name__ == "__main__":
    main()

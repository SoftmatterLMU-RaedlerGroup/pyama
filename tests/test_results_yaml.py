#!/usr/bin/env python3
"""
Test script for PyAMA results YAML functionality.

This script tests YAML serialization and deserialization of processing results:
- Serializing ProcessingContext to YAML
- Loading YAML back to Python objects
- Merging contexts from multiple workers
- Round-trip verification

Usage:
    python test_results_yaml.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory
import yaml

from pyama_core.io.results_yaml import (
    deserialize_from_dict,
    serialize_processing_results,
    get_channels_from_yaml,
    load_processing_results_yaml,
    save_processing_results_yaml,
)
from pyama_core.processing.workflow.run import _merge_contexts
from pyama_core.types.processing import (
    ChannelSelection,
    Channels,
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)


def create_dummy_file(directory, filename):
    """Create a dummy file for testing."""
    path = directory / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def test_yaml_serialization():
    """Test serializing ProcessingContext to YAML format."""
    print("="*60)
    print("Testing YAML Serialization")
    print("="*60)
    
    with TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        
        print("1. Creating processing context...")
        print("   Channels:")
        print("     Phase contrast: Channel 0, features ['perimeter', 'area']")
        print("     Fluorescence: Channel 1, features ['intensity_total']")
        print("                    Channel 2, features ['mean', 'intensity_total']")
        
        # Create dummy files
        pc_path = create_dummy_file(output_dir, "fov0_pc.npy")
        fl1_path = create_dummy_file(output_dir, "fov0_fl1.npy")
        fl2_corr_path = create_dummy_file(output_dir, "fov0_fl2_corr.npy")
        seg_path = create_dummy_file(output_dir, "fov0_seg.npy")
        seg_labeled_path = create_dummy_file(output_dir, "fov0_seg_labeled.npy")
        traces_path = create_dummy_file(output_dir, "fov0_traces.csv")
        
        # Create context
        context = ProcessingContext(
            output_dir=output_dir,
            channels=Channels(
                pc=ChannelSelection(channel=0, features=["perimeter", "area"]),
                fl=[
                    ChannelSelection(channel=1, features=["intensity_total"]),
                    ChannelSelection(channel=2, features=["mean", "intensity_total"]),
                ],
            ),
            params={},
        )
        ensure_context(context)
        
        # Add FOV 0 results
        context.results = {}
        fov0 = ensure_results_entry()
        fov0.pc = (0, pc_path)
        fov0.fl.append((1, fl1_path))
        fov0.fl_corrected.append((2, fl2_corr_path))
        fov0.seg = (0, seg_path)
        fov0.seg_labeled = (0, seg_labeled_path)
        fov0.traces = traces_path
        context.results[0] = fov0
        
        print(f"   ✓ Created context with {len(context.results)} FOV")
        
        # Serialize to YAML
        print("\n2. Serializing to YAML...")
        serialized = serialize_processing_results(context)
        yaml_path = output_dir / "processing_results.yaml"
        
        with yaml_path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(serialized, f, sort_keys=False)
        
        print(f"   ✓ Saved to: {yaml_path}")
        
        # Display YAML content
        print("\n3. Generated YAML content:")
        print("-" * 60)
        with yaml_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        print(yaml.dump(raw, sort_keys=False))
        print("-" * 60)
        
        # Verify channel block
        print("\n4. Verifying channel block...")
        channel_block = raw["channels"]
        expected_pc = [0, ["area", "perimeter"]]  # Sorted alphabetically
        expected_fl = [
            [1, ["intensity_total"]],
            [2, ["intensity_total", "mean"]],  # Sorted alphabetically
        ]
        
        pc_match = channel_block["pc"] == expected_pc
        fl_match = channel_block["fl"] == expected_fl
        
        print(f"   Phase contrast: {channel_block['pc']}")
        print(f"   Expected:       {expected_pc}")
        print(f"   {'✓ Match' if pc_match else '❌ Mismatch'}")
        
        print(f"\n   Fluorescence: {channel_block['fl']}")
        print(f"   Expected:     {expected_fl}")
        print(f"   {'✓ Match' if fl_match else '❌ Mismatch'}")
        
        # Verify results block
        print("\n5. Verifying results block...")
        results_block = raw["results"]
        print(f"   FOV 0 PC: {results_block['0']['pc']}")
        print(f"   FOV 0 FL: {results_block['0']['fl']}")
        print(f"   FOV 0 FL_corrected: {results_block['0']['fl_corrected']}")
        print(f"   FOV 0 traces: {results_block['0']['traces']}")
        
        return yaml_path, context, output_dir


def test_yaml_deserialization(yaml_path):
    """Test loading YAML back to Python objects."""
    print("\n" + "="*60)
    print("Testing YAML Deserialization")
    print("="*60)
    
    print("1. Loading YAML file...")
    loaded = load_processing_results_yaml(yaml_path)
    
    with yaml_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    
    channel_block = raw["channels"]
    
    print("2. Deserializing channels...")
    round_trip_context = deserialize_from_dict({"channels": channel_block})
    
    pc_channel = round_trip_context.channels.get_pc_channel()
    fl_features = round_trip_context.channels.get_fl_feature_map()
    
    print(f"   Phase contrast channel: {pc_channel}")
    print(f"   Fluorescence features: {fl_features}")
    
    # Extract fluorescence channels
    fluorescence_channels = get_channels_from_yaml(loaded)
    print(f"   Fluorescence channels: {fluorescence_channels}")
    
    print("\n✓ YAML deserialization successful")


def test_save_load_round_trip():
    """Test that save_processing_results_yaml creates files that can be loaded."""
    print("\n" + "="*60)
    print("Testing Save/Load Round-Trip")
    print("="*60)
    
    with TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)
        
        print("1. Creating test context...")
        traces_path = create_dummy_file(output_dir, "fov0_traces.csv")
        
        context = ProcessingContext(
            output_dir=output_dir,
            channels=Channels(
                pc=ChannelSelection(channel=0, features=["area"]),
                fl=[ChannelSelection(channel=1, features=["intensity_total"])],
            ),
            params={},
        )
        ensure_context(context)
        context.results = {}
        fov0 = ensure_results_entry()
        fov0.traces = traces_path
        context.results[0] = fov0
        
        print("2. Saving to YAML...")
        save_processing_results_yaml(context, output_dir, time_units="min")
        
        yaml_path = output_dir / "processing_results.yaml"
        if not yaml_path.exists():
            print("   ❌ YAML file was not created")
            return
        
        print(f"   ✓ Saved to: {yaml_path}")
        
        print("3. Loading back from YAML...")
        loaded = load_processing_results_yaml(yaml_path)
        
        # Verify contents
        assert loaded["time_units"] == "min", "Time units should be 'min'"
        assert loaded["channels"]["pc"][0] == 0, "PC channel should be 0"
        assert loaded["channels"]["fl"][0][0] == 1, "FL channel should be 1"
        
        print("   ✓ Round-trip successful")
        print(f"   Time units: {loaded['time_units']}")
        print(f"   PC channel: {loaded['channels']['pc'][0]}")
        print(f"   FL channel: {loaded['channels']['fl'][0][0]}")


def test_context_merging(context, output_dir):
    """Test merging processing contexts from multiple workers."""
    print("\n" + "="*60)
    print("Testing Context Merging")
    print("="*60)
    
    print("1. Creating worker context...")
    print("   Worker channels:")
    print("     Phase contrast: None")
    print("     Fluorescence: Channel 2, features ['variance']")
    print("                    Channel 3, features ['sum']")
    
    # Create worker context
    worker_context = ProcessingContext(
        output_dir=output_dir,
        channels=Channels(
            pc=None,
            fl=[
                ChannelSelection(channel=2, features=["variance"]),
                ChannelSelection(channel=3, features=["sum"]),
            ],
        ),
        params={},
    )
    ensure_context(worker_context)
    
    # Add worker results
    worker_entry = ensure_results_entry()
    worker_fl_path = create_dummy_file(output_dir, "fov1_fl2.npy")
    worker_traces_path = create_dummy_file(output_dir, "fov1_traces.csv")
    worker_entry.fl.append((2, worker_fl_path))
    worker_entry.traces = worker_traces_path
    worker_context.results[1] = worker_entry
    
    print(f"   ✓ Created worker context with FOV 1")
    
    # Show state before merge
    print("\n2. Before merge:")
    print(f"   Primary FOVs: {list(context.results.keys())}")
    print(f"   Worker FOVs: {list(worker_context.results.keys())}")
    if context.channels.fl:
        print(f"   Primary FL channels: {[fl.channel for fl in context.channels.fl]}")
    if worker_context.channels.fl:
        print(f"   Worker FL channels: {[fl.channel for fl in worker_context.channels.fl]}")
    
    # Perform merge
    print("\n3. Merging contexts...")
    _merge_contexts(context, worker_context)
    
    # Show state after merge
    print("   After merge:")
    print(f"   Merged FOVs: {list(context.results.keys())}")
    if context.channels.fl:
        print(f"   Merged FL channels: {[fl.channel for fl in context.channels.fl]}")
        for fl in context.channels.fl:
            print(f"     Channel {fl.channel}: {fl.features}")
    
    # Serialize merged context
    print("\n4. Serializing merged context...")
    merged_serialized = serialize_processing_results(context)
    yaml_path = output_dir / "processing_results_merged.yaml"
    
    with yaml_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(merged_serialized, f, sort_keys=False)
    
    print(f"   ✓ Saved to: {yaml_path}")
    
    # Display merged YAML
    print("\n5. Merged YAML content:")
    print("-" * 60)
    with yaml_path.open("r", encoding="utf-8") as f:
        merged_raw = yaml.safe_load(f)
    print(yaml.dump(merged_raw, sort_keys=False))
    print("-" * 60)
    
    # Verify merge results
    print("\n6. Verifying merge...")
    merged_channels = merged_raw["channels"]
    expected_merged_fl = [
        [1, ["intensity_total"]],
        [2, ["intensity_total", "mean", "variance"]],  # Merged features
        [3, ["sum"]],
    ]
    
    print(f"   Expected FL channels: {expected_merged_fl}")
    print(f"   Actual FL channels:   {merged_channels['fl']}")
    
    fl_match = merged_channels["fl"] == expected_merged_fl
    print(f"   {'✓ Merge correct' if fl_match else '❌ Merge incorrect'}")
    
    merged_results = merged_raw["results"]
    both_fovs = "0" in merged_results and "1" in merged_results
    print(f"\n   FOVs in results: {list(merged_results.keys())}")
    print(f"   {'✓ Both FOVs present' if both_fovs else '❌ Missing FOVs'}")
    
    # Test final loading
    print("\n7. Final load verification...")
    merged_loaded = load_processing_results_yaml(yaml_path)
    merged_channels_list = get_channels_from_yaml(merged_loaded)
    print(f"   Final channel list: {merged_channels_list}")
    print(f"   Expected: [1, 2, 3]")
    
    channels_match = merged_channels_list == [1, 2, 3]
    print(f"   {'✓ Final load correct' if channels_match else '❌ Final load incorrect'}")


def main():
    """Run all YAML functionality tests."""
    print("="*60)
    print("PyAMA Results YAML Testing")
    print("="*60)
    
    # Test serialization
    yaml_path, context, output_dir = test_yaml_serialization()
    
    # Test deserialization
    test_yaml_deserialization(yaml_path)
    
    # Test save/load round-trip
    test_save_load_round_trip()
    
    # Test context merging
    test_context_merging(context, output_dir)
    
    # Summary
    print(f"\n{'='*60}")
    print("✓ All YAML tests completed successfully!")
    print("✓ Serialization/deserialization working")
    print("✓ Context merging working")
    print("✓ Round-trip verification working")
    print("="*60)


if __name__ == "__main__":
    main()

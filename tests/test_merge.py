#!/usr/bin/env python3
"""
Test script for PyAMA merge functionality.

This script tests merging processing results from multiple FOVs into tidy CSV files
for analysis. It tests:
- FOV range parsing
- Merge execution
- Channel-feature configuration extraction

Usage:
    python test_merge.py
"""

from pathlib import Path
import pandas as pd
import yaml
from tempfile import TemporaryDirectory

from pyama_core.processing.merge import (
    get_channel_feature_config,
    parse_fov_range,
    run_merge,
)
from pyama_core.io.results_yaml import load_processing_results_yaml


def test_fov_range_parsing():
    """Test parsing of FOV range strings like "0-2, 4, 6-7"."""
    print("="*60)
    print("Testing FOV Range Parsing")
    print("="*60)
    
    test_cases = [
        ("0-2, 4, 6-7", [0, 1, 2, 4, 6, 7]),
        ("1,3,5", [1, 3, 5]),
        ("0-5", [0, 1, 2, 3, 4, 5]),
        ("10-12, 15", [10, 11, 12, 15]),
    ]
    
    print("Test cases:")
    for input_str, expected in test_cases:
        result = parse_fov_range(input_str)
        status = "✓" if result == expected else "❌"
        print(f"   {status} '{input_str}' -> {result}")
        if result != expected:
            print(f"      Expected: {expected}")
    
    print("\n✓ FOV range parsing tests completed\n")


def test_merge_functionality():
    """Test merging processing results into tidy CSV files."""
    print("="*60)
    print("Testing Merge Functionality")
    print("="*60)
    
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create sample configuration YAML
        print("1. Creating sample configuration...")
        samples_yaml = tmp_path / "samples.yaml"
        samples_config = {
            "samples": [
                {
                    "name": "sample",
                    "fovs": "0"
                }
            ]
        }
        with samples_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(samples_config, f, sort_keys=False)
        
        print(f"   Created: {samples_yaml}")
        print(f"   Content:\n{yaml.dump(samples_config, sort_keys=False)}")
        
        # Create sample traces CSV
        print("\n2. Creating sample traces CSV...")
        traces_csv = tmp_path / "fov0_traces.csv"
        traces_data = pd.DataFrame({
            "fov": [0, 0],
            "time": [0.0, 1.0],
            "cell": [1, 1],
            "good": [True, True],
            "area_ch_0": [10.0, 12.0],
            "intensity_total_ch_1": [100.0, 110.0],
        })
        traces_data.to_csv(traces_csv, index=False)
        
        print(f"   Created: {traces_csv}")
        print(f"   Content:\n{traces_data.to_string()}")
        
        # Create processing results YAML
        print("\n3. Creating processing results YAML...")
        processing_yaml = tmp_path / "processing_results.yaml"
        processing_config = {
            "channels": {
                "pc": [0, ["area"]],
                "fl": [[1, ["intensity_total"]]],
            },
            "time_units": "min",
            "results": {
                "0": {"traces": str(traces_csv)},
            },
        }
        with processing_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(processing_config, f, sort_keys=False)
        
        print(f"   Created: {processing_yaml}")
        print(f"   Content:\n{yaml.dump(processing_config, sort_keys=False)}")
        
        # Run merge
        print("\n4. Running merge...")
        output_dir = tmp_path / "merged"
        message = run_merge(samples_yaml, processing_yaml, output_dir)
        print(f"   Result: {message}")
        
        # Check outputs
        print("\n5. Checking output files...")
        pc_output = output_dir / "sample_area_ch_0.csv"
        fl_output = output_dir / "sample_intensity_total_ch_1.csv"
        
        if pc_output.exists():
            print(f"   ✓ Phase contrast output: {pc_output.name}")
            pc_df = pd.read_csv(pc_output, comment="#")
            print(f"     Columns: {list(pc_df.columns)}")
            print(f"     Expected: ['time', 'fov', 'cell', 'value']")
            print(f"     Data:\n{pc_df.to_string()}")
            
            expected_columns = ["time", "fov", "cell", "value"]
            if list(pc_df.columns) == expected_columns:
                print("     ✓ Column format correct (tidy format)")
            else:
                print(f"     ❌ Column format incorrect")
        else:
            print(f"   ❌ Phase contrast output missing!")
        
        if fl_output.exists():
            print(f"\n   ✓ Fluorescence output: {fl_output.name}")
            fl_df = pd.read_csv(fl_output, comment="#")
            print(f"     Columns: {list(fl_df.columns)}")
            print(f"     Expected: ['time', 'fov', 'cell', 'value']")
            print(f"     Data:\n{fl_df.to_string()}")
            
            expected_columns = ["time", "fov", "cell", "value"]
            if list(fl_df.columns) == expected_columns:
                print("     ✓ Column format correct (tidy format)")
            else:
                print(f"     ❌ Column format incorrect")
        else:
            print(f"\n   ❌ Fluorescence output missing!")
        
        print("\n✓ Merge functionality tests completed\n")


def test_channel_feature_config():
    """Test extraction of channel-feature configuration from processing results."""
    print("="*60)
    print("Testing Channel-Feature Configuration Extraction")
    print("="*60)
    
    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        
        # Create sample CSV with multiple channels and features
        print("1. Creating sample CSV with multiple channels...")
        traces_csv = tmp_path / "fov0_traces.csv"
        csv_content = """time,cell,good,area_ch_0,perimeter_ch_0,intensity_total_ch_1,mean_ch_1,variance_ch_2
0,1,True,10,15,100,50,5
1,1,True,12,16,110,55,6
"""
        traces_csv.write_text(csv_content)
        print(f"   Created: {traces_csv}")
        print(f"   Content:\n{csv_content}")
        
        # Create processing results YAML
        print("\n2. Creating processing results YAML...")
        processing_yaml = tmp_path / "processing_results.yaml"
        processing_config = {
            "channels": {
                "pc": [0, ["area", "perimeter"]],
                "fl": [
                    [1, ["intensity_total", "mean"]],
                    [2, ["variance"]]
                ],
            },
            "time_units": "min",
            "results": {
                "0": {"traces": str(traces_csv)},
            },
        }
        with processing_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(processing_config, f, sort_keys=False)
        
        print(f"   Created: {processing_yaml}")
        print(f"   Content:\n{yaml.dump(processing_config, sort_keys=False)}")
        
        # Load and extract config
        print("\n3. Extracting channel-feature configuration...")
        proc_results = load_processing_results_yaml(processing_yaml)
        config = get_channel_feature_config(proc_results)
        
        print(f"   Extracted config: {config}")
        print(f"\n   Channel breakdown:")
        for channel_id, features in config.items():
            print(f"     Channel {channel_id}: {features}")
        
        # Verify expected structure
        expected_channels = {0: ["area", "perimeter"], 1: ["intensity_total", "mean"], 2: ["variance"]}
        print(f"\n   Expected: {expected_channels}")
        
        if config == expected_channels:
            print("   ✓ Configuration extraction correct")
        else:
            print("   ❌ Configuration extraction incorrect")
        
        print("\n✓ Channel-feature configuration tests completed\n")


def main():
    """Run all merge functionality tests."""
    print("="*60)
    print("PyAMA Merge Functionality Testing")
    print("="*60)
    print()
    
    test_fov_range_parsing()
    test_merge_functionality()
    test_channel_feature_config()
    
    print("="*60)
    print("✓ All merge tests completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()

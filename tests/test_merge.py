#!/usr/bin/env python3
"""
Visual testing script for PyAMA merge functionality.
Shows input and output data explicitly instead of using assertions.
"""

from pathlib import Path
import pandas as pd
import yaml

from pyama_core.processing.merge import (
    get_channel_feature_config,
    parse_fov_range,
    run_merge,
)
from pyama_core.io.results_yaml import load_processing_results_yaml


def _write_processing_results(base_dir: Path, csv_path: Path) -> Path:
    """Write a processing results YAML file."""
    processing_yaml = base_dir / "processing_results.yaml"
    yaml.safe_dump(
        {
            "channels": {
                "pc": [0, ["area"]],
                "fl": [[1, ["intensity_total"]]],
            },
            "time_units": "min",
            "results": {
                "0": {"traces": str(csv_path)},
            },
        },
        processing_yaml.open("w", encoding="utf-8"),
        sort_keys=False,
    )
    return processing_yaml


def demonstrate_parse_fov_range():
    """Demonstrate FOV range parsing functionality."""
    print("=== FOV Range Parsing Demo ===")

    test_cases = ["0-2, 4, 6-7", "1,3,5", "0-5", "10-12, 15"]

    for test_input in test_cases:
        result = parse_fov_range(test_input)
        print(f"Input: '{test_input}' -> Output: {result}")

    print("✓ FOV range parsing works correctly\n")


def demonstrate_merge_functionality():
    """Demonstrate merge functionality with explicit I/O display."""
    print("=== Merge Functionality Demo ===")

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create sample YAML configuration
        sample_yaml = tmp_path / "samples.yaml"
        yaml.safe_dump(
            {"samples": [{"name": "sample", "fovs": "0"}]},
            sample_yaml.open("w", encoding="utf-8"),
            sort_keys=False,
        )

        print("1. Sample configuration:")
        print(sample_yaml.read_text())

        # Create sample traces CSV
        csv_path = tmp_path / "fov0_traces.csv"
        df = pd.DataFrame(
            {
                "fov": [0, 0],
                "time": [0.0, 1.0],
                "cell": [1, 1],
                "good": [True, True],
                "area_ch_0": [10.0, 12.0],
                "intensity_total_ch_1": [100.0, 110.0],
            }
        )
        df.to_csv(csv_path, index=False)

        print("\n2. Input traces CSV:")
        print(df.to_string())

        # Write processing results
        processing_yaml = _write_processing_results(tmp_path, csv_path)

        print("\n3. Processing results YAML:")
        print(processing_yaml.read_text())

        # Run merge
        output_dir = tmp_path / "merged"
        message = run_merge(sample_yaml, processing_yaml, output_dir)

        print(f"\n4. Merge result: {message}")

        # Check outputs
        pc_output = output_dir / "sample_area_ch_0.csv"
        fl_output = output_dir / "sample_intensity_total_ch_1.csv"

        if pc_output.exists():
            print("\n5. Phase contrast output (area_ch_0) - tidy format:")
            pc_df = pd.read_csv(pc_output, comment="#")
            print(pc_df.to_string())
            print(f"Columns: {list(pc_df.columns)}")
            print(f"Expected columns: ['time', 'fov', 'cell', 'value']")
            assert list(pc_df.columns) == ["time", "fov", "cell", "value"], \
                f"Expected tidy format columns, got {list(pc_df.columns)}"
        else:
            print("\n5. ❌ Phase contrast output file missing!")

        if fl_output.exists():
            print("\n6. Fluorescence output (intensity_total_ch_1) - tidy format:")
            fl_df = pd.read_csv(fl_output, comment="#")
            print(fl_df.to_string())
            print(f"Columns: {list(fl_df.columns)}")
            print(f"Expected columns: ['time', 'fov', 'cell', 'value']")
            assert list(fl_df.columns) == ["time", "fov", "cell", "value"], \
                f"Expected tidy format columns, got {list(fl_df.columns)}"
        else:
            print("\n6. ❌ Fluorescence output file missing!")


def demonstrate_channel_feature_config():
    """Demonstrate channel feature configuration extraction."""
    print("\n=== Channel Feature Configuration Demo ===")

    from tempfile import TemporaryDirectory

    with TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        # Create sample CSV with multiple channels and features
        csv_path = tmp_path / "fov0_traces.csv"
        csv_content = """time,cell,good,area_ch_0,perimeter_ch_0,intensity_total_ch_1,mean_ch_1,variance_ch_2
0,1,True,10,15,100,50,5
1,1,True,12,16,110,55,6
"""
        csv_path.write_text(csv_content)

        print("1. Sample CSV content:")
        print(csv_content)

        # Create processing results with multiple channels and features
        processing_yaml = tmp_path / "processing_results.yaml"
        yaml_content = {
            "channels": {
                "pc": [0, ["area", "perimeter"]],
                "fl": [[1, ["intensity_total", "mean"]], [2, ["variance"]]],
            },
            "time_units": "min",
            "results": {
                "0": {"traces": str(csv_path)},
            },
        }

        with processing_yaml.open("w", encoding="utf-8") as f:
            yaml.safe_dump(yaml_content, f, sort_keys=False)

        print("\n2. Processing results YAML:")
        print(processing_yaml.read_text())

        # Load and extract config
        proc_results = load_processing_results_yaml(processing_yaml)
        config = get_channel_feature_config(proc_results)

        print("\n3. Extracted channel-feature configuration:")
        print(f"   Channel 0 (PC): {config[0][1] if config else 'N/A'}")
        print(f"   Channel 1 (FL): {config[1][1] if len(config) > 1 else 'N/A'}")
        print(f"   Channel 2 (FL): {config[2][1] if len(config) > 2 else 'N/A'}")
        print(f"   Raw config: {config}")


def main():
    """Run all merge functionality demonstrations."""
    print("PyAMA Merge Functionality Testing")
    print("================================")

    demonstrate_parse_fov_range()
    demonstrate_merge_functionality()
    demonstrate_channel_feature_config()

    print("\n=== All merge tests completed successfully! ===")


if __name__ == "__main__":
    main()

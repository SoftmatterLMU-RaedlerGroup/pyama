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


def test_parse_fov_range_handles_ranges_and_values():
    assert parse_fov_range("0-2, 4, 6-7") == [0, 1, 2, 4, 6, 7]


def test_run_merge_generates_pc_and_fl_outputs(tmp_path: Path):
    sample_yaml = tmp_path / "samples.yaml"
    yaml.safe_dump(
        {"samples": [{"name": "sample", "fovs": "0"}]},
        sample_yaml.open("w", encoding="utf-8"),
        sort_keys=False,
    )

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

    processing_yaml = _write_processing_results(tmp_path, csv_path)

    output_dir = tmp_path / "merged"
    message = run_merge(sample_yaml, processing_yaml, tmp_path, output_dir)

    pc_output = output_dir / "sample_area_ch_0.csv"
    fl_output = output_dir / "sample_intensity_total_ch_1.csv"

    assert pc_output.exists()
    assert fl_output.exists()
    assert "Created 2 files" in message

    pc_df = pd.read_csv(pc_output, comment="#")
    assert list(pc_df.columns) == ["time", "fov_000_cell_1"]
    assert pc_df["fov_000_cell_1"].tolist() == [10.0, 12.0]

    fl_df = pd.read_csv(fl_output, comment="#")
    assert list(fl_df.columns) == ["time", "fov_000_cell_1"]
    assert fl_df["fov_000_cell_1"].tolist() == [100.0, 110.0]


def test_channel_feature_config_includes_pc_and_fl(tmp_path: Path):
    csv_path = tmp_path / "fov0_traces.csv"
    csv_path.write_text("time,cell,good,area_ch_0\n0,1,True,10\n")
    processing_yaml = _write_processing_results(tmp_path, csv_path)
    proc_results = load_processing_results_yaml(processing_yaml)

    config = get_channel_feature_config(proc_results)
    assert config == [(0, ["area"]), (1, ["intensity_total"])]

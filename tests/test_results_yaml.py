"""Unit tests for processing_results.yaml helpers."""

from pathlib import Path

import pytest
import yaml

from pyama_core.io.results_yaml import (
    get_channels_from_yaml,
    get_time_units_from_yaml,
    get_trace_csv_path_from_yaml,
    load_processing_results_yaml,
)
from pyama_core.processing.workflow.run import _paths_to_strings
from pyama_core.processing.workflow.services.types import ProcessingContext


def _write_processing_results(tmp_path, data: dict) -> Path:
    """Serialize a processing results dict to YAML under tmp_path."""
    yaml_path = tmp_path / "processing_results.yaml"
    with yaml_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)
    return yaml_path


def test_load_processing_results_yaml_round_trip(tmp_path):
    """Processing results YAML should round-trip via load helper."""
    raw_data = {
        "project_path": str(tmp_path),
        "n_fov": 1,
        "channels": {
            "pc": {"channel": 0, "features": ["area", "perimeter"]},
            "fl": [
                {"channel": 1, "features": ["intensity_total"]},
                {"channel": 2, "features": ["mean", "sum"]},
            ],
        },
        "fov_data": {"0": {"traces": "fov0_traces.csv"}},
        "time_units": "min",
        "extra": {"note": "unit-test"},
    }
    yaml_path = _write_processing_results(tmp_path, raw_data)

    loaded = load_processing_results_yaml(yaml_path)

    assert loaded == raw_data
    assert loaded["project_path"] == raw_data["project_path"]
    assert loaded["fov_data"]["0"]["traces"] == "fov0_traces.csv"


def test_get_channels_from_yaml_normalizes_payloads():
    """Channel helper should normalize fluorescence channels to IDs."""
    processing_results = {
        "channels": {
            "pc": {"channel": 5, "features": ["foo"]},
            "fl": [
                {"channel": 3, "features": ["b", "a"]},
                {"channel": 7, "features": ["x"]},
            ],
        }
    }

    channels = get_channels_from_yaml(processing_results)

    assert sorted(channels) == [3, 7]


def test_get_trace_csv_path_from_yaml_accepts_string_keys(tmp_path):
    """Trace path helper should resolve FOV entries stored with string keys."""
    processing_results = {
        "fov_data": {
            "0": {"traces": str(tmp_path / "fov0_traces.csv")},
            1: {"traces": str(tmp_path / "fov1_traces.csv")},
        }
    }

    path_fov0 = get_trace_csv_path_from_yaml(processing_results, 0)
    path_fov1 = get_trace_csv_path_from_yaml(processing_results, 1)
    path_missing = get_trace_csv_path_from_yaml(processing_results, 2)

    assert path_fov0 == tmp_path / "fov0_traces.csv"
    assert path_fov1 == tmp_path / "fov1_traces.csv"
    assert path_missing is None


def test_get_time_units_from_yaml_returns_value():
    processing_results = {"time_units": "min"}
    assert get_time_units_from_yaml(processing_results) == "min"


def test_paths_to_strings_converts_nested_paths(tmp_path):
    csv_path = tmp_path / "fov0_traces.csv"
    csv_path.write_text("dummy")
    context: ProcessingContext = {
        "results": {
            0: {
                "traces": csv_path,
            }
        }
    }

    stringified = _paths_to_strings(context)

    assert stringified["results"][0]["traces"] == str(csv_path)

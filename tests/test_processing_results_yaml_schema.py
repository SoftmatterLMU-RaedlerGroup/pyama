from pathlib import Path
from tempfile import TemporaryDirectory
import yaml

from pyama_core.processing.workflow.services.types import (
    Channels,
    ProcessingContext,
    ensure_context,
    ensure_results_entry,
)
from pyama_core.processing.workflow.pipeline import (
    _serialize_for_yaml,
    _deserialize_from_dict,
    _merge_contexts,
)
from pyama_core.io.results_yaml import (
    get_channels_from_yaml,
    load_processing_results_yaml,
)


def main() -> None:
    with TemporaryDirectory() as tmp_dir:
        output_dir = Path(tmp_dir)

        def touch(name: str) -> Path:
            path = output_dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"")
            return path

        # Seed primary context with channel selections and concrete results
        pc_path = touch("fov0_pc.npy")
        fl_raw_path = touch("fov0_fl1.npy")
        fl_corr_path = touch("fov0_fl2_corr.npy")
        seg_path = touch("fov0_seg.npy")
        seg_labeled_path = touch("fov0_seg_labeled.npy")
        traces_path = touch("fov0_traces.csv")

        context = ProcessingContext(
            output_dir=output_dir,
            channels=Channels.from_feature_mapping(
                pc_channel=0,
                pc_features=["perimeter", "area"],
                fl_features={2: ["mean", "intensity_total"], 1: ["intensity_total"]},
            ),
            params={},
        )
        context.results = {}
        fov0 = ensure_results_entry()
        fov0.pc = (0, pc_path)
        fov0.fl.append((1, fl_raw_path))
        fov0.fl_corrected.append((2, fl_corr_path))
        fov0.seg = (0, seg_path)
        fov0.seg_labeled = (0, seg_labeled_path)
        fov0.traces = traces_path
        context.results[0] = fov0

        ensure_context(context)

        serialized = _serialize_for_yaml(context)
        yaml_path = output_dir / "processing_results.yaml"
        with yaml_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(serialized, handle, sort_keys=False)

        with yaml_path.open("r", encoding="utf-8") as handle:
            raw = yaml.safe_load(handle)

        channel_block = raw["channels"]

        assert channel_block["pc"] == [0, ["area", "perimeter"]]
        assert channel_block["fl"] == [
            [1, ["intensity_total"]],
            [2, ["intensity_total", "mean"]],
        ]

        results_block = raw["results"]
        assert results_block["0"]["pc"] == [0, str(pc_path)]
        assert results_block["0"]["fl"] == [[1, str(fl_raw_path)]]
        assert results_block["0"]["fl_corrected"] == [[2, str(fl_corr_path)]]
        assert results_block["0"]["seg"] == [0, str(seg_path)]
        assert results_block["0"]["seg_labeled"] == [0, str(seg_labeled_path)]
        assert results_block["0"]["traces"] == str(traces_path)

        loaded = load_processing_results_yaml(yaml_path)
        round_trip_context = _deserialize_from_dict({"channels": channel_block})
        assert round_trip_context.channels.get_pc_channel() == 0
        assert round_trip_context.channels.get_fl_feature_map()[2] == [
            "intensity_total",
            "mean",
        ]

        fluorescence_channels = get_channels_from_yaml(loaded)
        assert fluorescence_channels == [1, 2]

        # Merge in a worker context with additional channels and FOV results
        worker_context = ProcessingContext(
            output_dir=output_dir,
            channels=Channels.from_feature_mapping(
                fl_features={2: ["variance"], 3: ["sum"]},
            ),
            params={},
        )
        ensure_context(worker_context)
        worker_entry = ensure_results_entry()
        worker_fl_path = touch("fov1_fl2.npy")
        worker_traces_path = touch("fov1_traces.csv")
        worker_entry.fl.append((2, worker_fl_path))
        worker_entry.traces = worker_traces_path
        worker_context.results[1] = worker_entry

        _merge_contexts(context, worker_context)

        merged_serialized = _serialize_for_yaml(context)
        with yaml_path.open("w", encoding="utf-8") as handle:
            yaml.safe_dump(merged_serialized, handle, sort_keys=False)

        with yaml_path.open("r", encoding="utf-8") as handle:
            merged_raw = yaml.safe_load(handle)

        merged_channels = merged_raw["channels"]
        assert merged_channels["fl"] == [
            [1, ["intensity_total"]],
            [2, ["intensity_total", "mean", "variance"]],
            [3, ["sum"]],
        ]

        merged_results = merged_raw["results"]
        assert "0" in merged_results and "1" in merged_results
        assert merged_results["1"]["fl"] == [[2, str(worker_fl_path)]]
        assert merged_results["1"]["traces"] == str(worker_traces_path)

        merged_processing = load_processing_results_yaml(yaml_path)
        merged_channels_list = get_channels_from_yaml(merged_processing)
        assert merged_channels_list == [1, 2, 3]

        print("YAML channel schema merge round-trip OK")


if __name__ == "__main__":
    main()

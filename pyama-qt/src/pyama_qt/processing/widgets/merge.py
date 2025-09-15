#!/usr/bin/env python3
from __future__ import annotations

# This module contains the reusable MergeSamplesPanel widget and the CLI-agnostic
# merge logic wrapper for the GUI to call.

import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Tuple, TypedDict, Optional

from PySide6 import QtWidgets


class FovCsvRow(TypedDict):
    fov: int
    time: float
    cell: int
    good: bool
    exist: bool
    feature_1: float
    feature_2: float


class SampleSpec(TypedDict):
    name: str
    fovs: List[int]


class ConfigFile(TypedDict):
    samples: List[SampleSpec]


# Output rows have dynamic measurement columns (e.g., "fov_000_cell_000").
# We declare time explicitly and allow additional optional keys via total=False.
class FeatureOutputRow(TypedDict, total=False):
    time: float
    # dynamic measurement columns with keys like "fov_000_cell_000": float


# -------------------------
# Utility functions
# -------------------------


def parse_bool(s: str) -> bool:
    return str(s).strip().lower() == "true"


def read_yaml_config(path: Path) -> ConfigFile:
    try:
        import yaml  # type: ignore
    except ImportError as e:
        raise SystemExit(
            "PyYAML is required to parse YAML. Please install with `pip install PyYAML`."
        ) from e

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
        # Basic shape validation
        if not isinstance(data, dict) or "samples" not in data:
            raise ValueError("YAML must contain a top-level 'samples' key")
        return data  # type: ignore[return-value]


def read_fov_csv(path: Path) -> List[FovCsvRow]:
    rows: List[FovCsvRow] = []
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        expected_fields = {
            "fov",
            "time",
            "cell",
            "good",
            "exist",
            "feature_1",
            "feature_2",
        }
        missing = expected_fields - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"CSV {path} is missing fields: {sorted(missing)}")

        for r in reader:
            row: FovCsvRow = {
                "fov": int(r["fov"]),
                "time": float(r["time"]),
                "cell": int(r["cell"]),
                "good": parse_bool(r["good"]),
                "exist": parse_bool(r["exist"]),
                # float('nan') handles 'NaN' and 'nan' inputs gracefully
                "feature_1": float(r["feature_1"])
                if r["feature_1"] != ""
                else float("nan"),
                "feature_2": float(r["feature_2"])
                if r["feature_2"] != ""
                else float("nan"),
            }
            rows.append(row)
    return rows


@dataclass(frozen=True)
class FeatureMaps:
    # (time, cell) -> value
    feature_1: Dict[Tuple[float, int], float]
    feature_2: Dict[Tuple[float, int], float]
    times: List[float]
    cells: List[int]


def build_feature_maps(rows: List[FovCsvRow]) -> FeatureMaps:
    f1: Dict[Tuple[float, int], float] = {}
    f2: Dict[Tuple[float, int], float] = {}
    times_set = set()
    cells_set = set()
    for r in rows:
        key = (r["time"], r["cell"])
        f1[key] = r["feature_1"]
        f2[key] = r["feature_2"]
        times_set.add(r["time"])
        cells_set.add(r["cell"])

    times = sorted(times_set)
    cells = sorted(cells_set)
    return FeatureMaps(f1, f2, times, cells)


def ensure_all_times_align(
    feature_maps_by_fov: Dict[int, FeatureMaps], fovs: Iterable[int]
) -> List[float]:
    # Union of times across the fovs in use, sorted
    union_times = set()
    for fov in fovs:
        fm = feature_maps_by_fov.get(fov)
        if fm is None:
            continue
        union_times.update(fm.times)
    return sorted(union_times)


# -------------------------
# Utility functions
# -------------------------


def parse_fovs_field(fovs_value) -> List[int]:
    """Parse FOV specifications from YAML.
    Accepts either:
      - list of ints (or numbers coercible to int)
      - string with comma-separated items and optional ranges like '1-5,6,8,9-11'
    Rules:
      - Only commas are allowed as separators (no semicolons)
      - Spaces are ignored
      - Ranges use 'start-end' inclusive, start <= end, non-negative integers
    Returns a sorted, de-duplicated list of ints.
    """
    result: List[int] = []

    if isinstance(fovs_value, list):
        for v in fovs_value:
            try:
                i = int(v)
            except Exception as e:
                raise ValueError(f"FOV value '{v}' is not an integer") from e
            if i < 0:
                raise ValueError(f"FOV value '{i}' must be >= 0")
            result.append(i)
    elif isinstance(fovs_value, str):
        normalized = fovs_value.replace(" ", "")
        if ";" in normalized:
            raise ValueError(
                "Invalid FOV spec: semicolons are not allowed. Use commas."
            )
        if normalized == "":
            raise ValueError("FOV spec cannot be empty")
        parts = [p for p in normalized.split(",") if p != ""]
        for p in parts:
            if "-" in p:
                a_b = p.split("-")
                if len(a_b) != 2 or a_b[0] == "" or a_b[1] == "":
                    raise ValueError(
                        f"Invalid range '{p}'. Use start-end with non-negative integers."
                    )
                a_str, b_str = a_b
                if not a_str.isdigit() or not b_str.isdigit():
                    raise ValueError(
                        f"Invalid range '{p}': endpoints must be non-negative integers."
                    )
                a, b = int(a_str), int(b_str)
                if a < 0 or b < 0:
                    raise ValueError(
                        f"Invalid range '{p}': negative values not allowed."
                    )
                if a > b:
                    raise ValueError(f"Invalid range '{p}': start must be <= end.")
                result.extend(range(a, b + 1))
            else:
                if not p.isdigit():
                    raise ValueError(
                        f"Invalid FOV '{p}': must be a non-negative integer."
                    )
                i = int(p)
                if i < 0:
                    raise ValueError(f"FOV value '{i}' must be >= 0")
                result.append(i)
    else:
        raise ValueError("FOV spec must be a list of ints or a comma-separated string.")

    if not result:
        raise ValueError("At least one FOV must be specified.")

    return sorted(set(result))


# -------------------------
# Writing outputs
# -------------------------


def write_feature_csv(
    out_path: Path,
    times: List[float],
    fovs: List[int],
    feature_name: str,  # "feature_1" | "feature_2"
    feature_maps_by_fov: Dict[int, FeatureMaps],
):
    # Build header: time + for each fov, for each cell: fov_XXX_cell_YYY
    column_names: List[str] = ["time"]

    # Gather cells per fov to keep header deterministic per fov
    cells_by_fov: Dict[int, List[int]] = {}
    for fov in fovs:
        fm = feature_maps_by_fov.get(fov)
        if fm is None:
            cells_by_fov[fov] = []
        else:
            cells_by_fov[fov] = fm.cells
        for cell in cells_by_fov[fov]:
            column_names.append(f"fov_{fov:03d}_cell_{cell:03d}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=column_names)
        writer.writeheader()

        for t in times:
            row: FeatureOutputRow = {"time": t}
            for fov in fovs:
                fm = feature_maps_by_fov.get(fov)
                # If feature map missing for this fov, leave cells empty
                cells = cells_by_fov.get(fov, [])
                for cell in cells:
                    key = f"fov_{fov:03d}_cell_{cell:03d}"
                    if fm is None:
                        row[key] = ""  # missing
                        continue
                    val = (
                        fm.feature_1.get((t, cell))
                        if feature_name == "feature_1"
                        else fm.feature_2.get((t, cell))
                    )
                    if val is None:
                        row[key] = ""
                    elif isinstance(val, float) and math.isnan(val):
                        # Preserve NaNs explicitly as 'NaN'
                        row[key] = "NaN"
                    else:
                        row[key] = val
            writer.writerow(row)


# -------------------------
# Orchestration used by GUI
# -------------------------


def run_merge(
    root: Path,
    sample_yaml: Optional[Path] = None,
    input_dir: Optional[Path] = None,
    output_dir: Optional[Path] = None,
) -> None:
    input_dir = input_dir or (root / "data")
    output_dir = output_dir or (root / "processed")
    config_path = sample_yaml or (input_dir / "sample.yaml")
    cfg = read_yaml_config(config_path)

    # Collect unique fovs needed (parse string or list forms)
    required_fovs: List[int] = sorted(
        {fov for s in cfg["samples"] for fov in parse_fovs_field(s.get("fovs", []))}
    )

    # Load each required fov CSV and build feature maps
    feature_maps_by_fov: Dict[int, FeatureMaps] = {}
    for fov in required_fovs:
        fov_path = input_dir / f"fov_{fov:03d}.csv"
        if not fov_path.exists():
            raise FileNotFoundError(f"Expected CSV for fov {fov}: {fov_path}")
        rows = read_fov_csv(fov_path)
        feature_maps_by_fov[fov] = build_feature_maps(rows)

    # For each sample, compute union times (across its fovs), and write both features
    for sample in cfg["samples"]:
        sample_name = sample["name"]
        sample_fovs = parse_fovs_field(sample.get("fovs", []))
        times = ensure_all_times_align(feature_maps_by_fov, sample_fovs)

        # feature_1
        out1 = output_dir / f"{sample_name}_feature_1.csv"
        write_feature_csv(out1, times, sample_fovs, "feature_1", feature_maps_by_fov)

        # feature_2
        out2 = output_dir / f"{sample_name}_feature_2.csv"
        write_feature_csv(out2, times, sample_fovs, "feature_2", feature_maps_by_fov)


class MergeSamplesPanel(QtWidgets.QWidget):
    """Reusable QWidget containing the merge UI (no app/exec)."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        # Top-level group: Merge Samples
        merge_group = QtWidgets.QGroupBox("Merge Samples")
        merge_layout = QtWidgets.QVBoxLayout(merge_group)

        # Sample YAML selector
        self.sample_edit = QtWidgets.QLineEdit(self)
        btn_sample = QtWidgets.QPushButton("Browse", self)
        btn_sample.clicked.connect(self._choose_sample)
        row1 = QtWidgets.QHBoxLayout()
        row1.addWidget(QtWidgets.QLabel("Sample YAML:", self))
        row1.addWidget(self.sample_edit)
        row1.addWidget(btn_sample)
        merge_layout.addLayout(row1)

        # Data directory selector
        self.data_edit = QtWidgets.QLineEdit(self)
        btn_data = QtWidgets.QPushButton("Browse", self)
        btn_data.clicked.connect(self._choose_data_dir)
        row2 = QtWidgets.QHBoxLayout()
        row2.addWidget(QtWidgets.QLabel("CSV folder:", self))
        row2.addWidget(self.data_edit)
        row2.addWidget(btn_data)
        merge_layout.addLayout(row2)

        # Output directory selector
        self.output_edit = QtWidgets.QLineEdit(self)
        btn_output = QtWidgets.QPushButton("Browse", self)
        btn_output.clicked.connect(self._choose_output_dir)
        row3 = QtWidgets.QHBoxLayout()
        row3.addWidget(QtWidgets.QLabel("Output folder:", self))
        row3.addWidget(self.output_edit)
        row3.addWidget(btn_output)
        merge_layout.addLayout(row3)

        # Action buttons
        actions = QtWidgets.QHBoxLayout()
        self.run_btn = QtWidgets.QPushButton("Run Merge", self)
        self.run_btn.clicked.connect(self._run_merge)
        actions.addWidget(self.run_btn)
        actions.addStretch(1)
        merge_layout.addLayout(actions)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(merge_group)

        # Initialize defaults (no prefill)
        self.sample_edit.clear()
        self.data_edit.clear()
        self.output_edit.clear()

    # ------- Helpers -------
    def _choose_sample(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select sample.yaml",
            str(Path(self.sample_edit.text()).parent),
            "YAML Files (*.yaml *.yml)",
        )
        if path:
            self.sample_edit.setText(path)

    def _choose_data_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select FOV CSV folder",
            str(
                Path(self.data_edit.text()).parent
                if self.data_edit.text()
                else Path.cwd()
            ),
        )
        if path:
            self.data_edit.setText(path)

    def _choose_output_dir(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select output folder",
            str(
                Path(self.output_edit.text()).parent
                if self.output_edit.text()
                else Path.cwd()
            ),
        )
        if path:
            self.output_edit.setText(path)

    def _run_merge(self) -> None:
        sample_path = Path(self.sample_edit.text()).expanduser()
        data_dir = Path(self.data_edit.text()).expanduser()
        output_dir = Path(self.output_edit.text()).expanduser()

        if not sample_path.exists():
            QtWidgets.QMessageBox.critical(
                self, "Error", f"Sample YAML not found:\n{sample_path}"
            )
            return
        if not data_dir.exists() or not data_dir.is_dir():
            QtWidgets.QMessageBox.critical(
                self, "Error", f"FOV CSV folder is invalid:\n{data_dir}"
            )
            return
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            run_merge(
                root=Path.cwd(),
                sample_yaml=sample_path,
                input_dir=data_dir,
                output_dir=output_dir,
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Merge Failed", f"An error occurred:\n{e}"
            )
            return

        QtWidgets.QMessageBox.information(
            self, "Success", f"Merge completed. Files written to:\n{output_dir}"
        )

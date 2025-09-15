from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any

from PySide6 import QtCore, QtWidgets
import yaml


class SampleTable(QtWidgets.QTableWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        # Use default selection behavior/mode and edit triggers from PySide6
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        name_item = QtWidgets.QTableWidgetItem("")
        fovs_item = QtWidgets.QTableWidgetItem("")
        # Enable editing
        name_item.setFlags(name_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | QtCore.Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QtWidgets.QTableWidgetItem(name))
        self.setItem(row, 1, QtWidgets.QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        # remove bottom-up to keep indexes stable
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(idx.row())

    def to_samples(self) -> List[Dict[str, Any]]:
        samples: List[Dict[str, Any]] = []
        seen_names: set[str] = set()
        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()

            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required.")
            if name in seen_names:
                raise ValueError(
                    f"Duplicate sample name '{name}' (row {row + 1}). Names must be unique."
                )
            seen_names.add(name)

            # Parse FOVs: only commas allowed as separators; spaces are ignored
            fovs: List[int] = []
            if fovs_text:
                normalized = fovs_text.replace(" ", "")
                if ";" in normalized:
                    raise ValueError(
                        f"Row {row + 1} ('{name}'): Use commas to separate FOVs (semicolons are not allowed)."
                    )
                parts = [p for p in normalized.split(",") if p != ""]
                for p in parts:
                    if "-" in p:
                        rng = p.split("-")
                        if len(rng) != 2 or rng[0] == "" or rng[1] == "":
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): Invalid range '{p}'. Use start-end with non-negative integers."
                            )
                        a_str, b_str = rng
                        if not a_str.isdigit() or not b_str.isdigit():
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): Range '{p}' must be non-negative integers."
                            )
                        a, b = int(a_str), int(b_str)
                        if a < 0 or b < 0:
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): Range '{p}' contains negative values."
                            )
                        if a > b:
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): Range start {a} must be <= end {b}."
                            )
                        fovs.extend(range(a, b + 1))
                    else:
                        if not p.isdigit():
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): FOV '{p}' is not a non-negative integer."
                            )
                        f = int(p)
                        if f < 0:
                            raise ValueError(
                                f"Row {row + 1} ('{name}'): FOV '{p}' must be >= 0."
                            )
                        fovs.append(f)
            if not fovs:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required."
                )
            # Deduplicate and sort
            fovs = sorted(set(fovs))

            samples.append({"name": name, "fovs": fovs})
        return samples

    def load_samples(self, samples: List[Dict[str, Any]]) -> None:
        self.setRowCount(0)
        for s in samples:
            name = str(s.get("name", ""))
            fovs_val = s.get("fovs", [])
            if isinstance(fovs_val, list):
                fovs_text = ", ".join(str(int(v)) for v in fovs_val)
            elif isinstance(fovs_val, str):
                # show exactly as stored
                fovs_text = fovs_val
            else:
                fovs_text = ""
            self.add_row(name, fovs_text)


class AssignFovsPanel(QtWidgets.QWidget):
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)

        self.table = SampleTable()

        self.add_btn = QtWidgets.QPushButton("Add Sample")
        self.remove_btn = QtWidgets.QPushButton("Remove Selected")
        self.load_btn = QtWidgets.QPushButton("Load from YAML")
        self.save_btn = QtWidgets.QPushButton("Save to YAML")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.add_btn)
        btn_row.addWidget(self.remove_btn)
        btn_row.addStretch(1)
        btn_row.addWidget(self.load_btn)
        btn_row.addWidget(self.save_btn)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addLayout(btn_row)
        layout.addWidget(self.table)

        self.add_btn.clicked.connect(self.table.add_empty_row)
        self.remove_btn.clicked.connect(self.table.remove_selected_row)
        self.load_btn.clicked.connect(self.on_load)
        self.save_btn.clicked.connect(self.on_save)

        # no auto-load on startup

    def on_load(self) -> None:
        try:
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Open sample.yaml",
                "",
                "YAML Files (*.yaml *.yml);;All Files (*)",
            )
            if not file_path:
                return
            path = Path(file_path)
            with path.open("r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            samples = data.get("samples", []) if isinstance(data, dict) else []
            if not isinstance(samples, list):
                raise ValueError("Invalid YAML format: 'samples' must be a list.")
            self.table.load_samples(samples)
            QtWidgets.QMessageBox.information(
                self, "Load", f"Loaded samples from:\n{path}"
            )
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Load Error", str(e))

    def on_save(self) -> None:
        try:
            # Collect rows exactly as typed
            samples_save: List[Dict[str, Any]] = []
            seen_names: set[str] = set()
            for row in range(self.table.rowCount()):
                name_item = self.table.item(row, 0)
                fovs_item = self.table.item(row, 1)
                name_typed = name_item.text() if name_item else ""
                fovs_typed = fovs_item.text() if fovs_item else ""
                name = name_typed.strip()
                if not name:
                    raise ValueError(f"Row {row + 1}: Sample name is required.")
                if name in seen_names:
                    raise ValueError(
                        f"Duplicate sample name '{name}' (row {row + 1}). Names must be unique."
                    )
                seen_names.add(name)
                if fovs_typed == "":
                    raise ValueError(
                        f"Row {row + 1} ('{name}'): FOVs field is required."
                    )
                # Save FOVs exactly as typed by the user (no parsing/normalization)
                samples_save.append({"name": name, "fovs": fovs_typed})

            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Save sample.yaml",
                "",
                "YAML Files (*.yaml *.yml);;All Files (*)",
            )
            if not file_path:
                return
            path = Path(file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            out = {"samples": samples_save}
            with path.open("w", encoding="utf-8") as f:
                yaml.safe_dump(out, f, sort_keys=False)
            QtWidgets.QMessageBox.information(self, "Saved", f"Wrote YAML to:\n{path}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Save Error", str(e))


def main() -> None:
    raise SystemExit("This widget module is not meant to be run directly. Use merging.main.")


if __name__ == "__main__":
    main()

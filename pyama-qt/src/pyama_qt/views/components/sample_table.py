from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QTableWidget,
    QHeaderView,
    QTableWidgetItem,
    QWidget,
)


class SampleTable(QTableWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels(["Sample Name", "FOVs (e.g., 0-5, 7, 9-11)"])
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setVisible(False)
        self.setAlternatingRowColors(True)

    def add_empty_row(self) -> None:
        row = self.rowCount()
        self.insertRow(row)
        name_item = QTableWidgetItem("")
        fovs_item = QTableWidgetItem("")
        name_item.setFlags(name_item.flags() | Qt.ItemFlag.ItemIsEditable)
        fovs_item.setFlags(fovs_item.flags() | Qt.ItemFlag.ItemIsEditable)
        self.setItem(row, 0, name_item)
        self.setItem(row, 1, fovs_item)
        self.setCurrentCell(row, 0)

    def add_row(self, name: str, fovs_text: str) -> None:
        row = self.rowCount()
        self.insertRow(row)
        self.setItem(row, 0, QTableWidgetItem(name))
        self.setItem(row, 1, QTableWidgetItem(fovs_text))

    def remove_selected_row(self) -> None:
        indexes = self.selectionModel().selectedRows()
        if not indexes:
            return
        for idx in sorted(indexes, key=lambda i: i.row(), reverse=True):
            self.removeRow(idx.row())

    def to_samples(self) -> list[dict[str, Any]]:
        """Convert table data to samples list with validation. Emit error if invalid."""
        samples = []
        seen_names = set()

        for row in range(self.rowCount()):
            name_item = self.item(row, 0)
            fovs_item = self.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            fovs_text = (fovs_item.text() if fovs_item else "").strip()

            # Validate name
            if not name:
                raise ValueError(f"Row {row + 1}: Sample name is required")
            if name in seen_names:
                raise ValueError(f"Row {row + 1}: Duplicate sample name '{name}'")
            seen_names.add(name)

            # Parse and validate FOVs
            if not fovs_text:
                raise ValueError(
                    f"Row {row + 1} ('{name}'): At least one FOV is required"
                )

            samples.append({"name": name, "fovs": fovs_text})

        return samples

    def load_samples(self, samples: list[dict[str, Any]]) -> None:
        """Load samples data into the table."""
        self.setRowCount(0)
        for sample in samples:
            name = str(sample.get("name", ""))
            fovs_val = sample.get("fovs", [])

            if isinstance(fovs_val, list):
                fovs_text = ", ".join(str(int(v)) for v in fovs_val)
            elif isinstance(fovs_val, str):
                fovs_text = fovs_val
            else:
                fovs_text = ""

            self.add_row(name, fovs_text)

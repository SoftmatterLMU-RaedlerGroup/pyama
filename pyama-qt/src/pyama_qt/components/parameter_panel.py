"""
ParameterPanel rewritten to present parameters in a table instead of label+editor rows.
The table infers fields from an input pandas DataFrame and allows editing when
"Set parameters manually" is enabled.
"""

from __future__ import annotations


import pandas as pd
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QCheckBox,
    QSizePolicy,
)
from PySide6.QtCore import Signal, Qt


class ParameterPanel(QWidget):
    """A widget that displays editable parameters in a table.

    Usage:
    - Preferred: set_parameters_df(df) with a DataFrame of defaults.
      The DataFrame should have parameter names as index OR include a 'name' column.
      All other columns are treated as fields (e.g., value, min, max...).
    - Backward-compatible: set_parameters(param_definitions) where each dict may
      include keys like name, default/value, min, max; these will be converted
      into a DataFrame with columns present in the definitions.
    - Call get_values_df() to retrieve an updated DataFrame if manual mode is enabled,
      or get_values() to retrieve the legacy dict format {"params": ..., "bounds": ...}.
    """

    parameters_changed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._df: pd.DataFrame | None = None
        self._fields: list[str] = []
        self._param_names: list[str] = []

        self.main_layout = QVBoxLayout(self)

        self.use_manual_params = QCheckBox("Set parameters manually")
        self.use_manual_params.stateChanged.connect(self.toggle_inputs)
        self.main_layout.addWidget(self.use_manual_params)

        self.table = QTableWidget(0, 0, self)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        # Emit change signal when any cell is edited
        self.table.itemChanged.connect(self._on_item_changed)
        self.main_layout.addWidget(self.table, 1)

        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.toggle_inputs()  # initialize disabled state

    # ---------------------------- Public API -------------------------------- #
    def set_parameters(self, param_definitions: list[dict]) -> None:
        """Backward-compatible entrypoint: accept list of param definitions.
        Converts to a DataFrame of fields and calls set_parameters_df.
        Supported keys per item: name (required), value/default, min, max, and any others.
        """
        if not param_definitions:
            self.set_parameters_df(pd.DataFrame())
            return
        rows = []
        for d in param_definitions:
            name = d.get("name")
            if name is None:
                continue
            row = {
                k: v
                for k, v in d.items()
                if k not in ("name", "label", "type", "choices", "show_bounds")
            }
            # Normalize default->value
            if "value" not in row and "default" in row:
                row["value"] = row.pop("default")
            row["name"] = name
            rows.append(row)
        df = pd.DataFrame(rows)
        # Ensure 'name' column exists
        if "name" not in df.columns:
            df.insert(0, "name", [f"param_{i}" for i in range(len(df))])
        self.set_parameters_df(df)

    def set_parameters_df(self, df: pd.DataFrame) -> None:
        """Initialize the table from a pandas DataFrame.

        - If a 'name' column exists, it is used as the row index and not shown as a field.
        - Otherwise, the DataFrame's index is used for parameter names.
        - All remaining columns are fields.
        """
        if df is None or df.empty:
            # Clear the table
            self._df = pd.DataFrame()
            self._fields = []
            self._param_names = []
            self._rebuild_table()
            return

        df_local = df.copy()
        if "name" in df_local.columns:
            df_local = df_local.set_index("name")
        # Normalize index to strings
        df_local.index = df_local.index.map(lambda x: str(x))

        self._df = df_local
        self._param_names = list(df_local.index)
        self._fields = list(df_local.columns)

        self._rebuild_table()
        self.toggle_inputs()

    def get_values_df(self) -> pd.DataFrame | None:
        """Return the current table as a DataFrame if manual mode is enabled; else None."""
        if not self.use_manual_params.isChecked():
            return None
        return self._collect_table_to_df()

    # Legacy API: keep compatibility with callers expecting dict of params/bounds
    def get_values(self) -> dict:
        """Return values in legacy dict format.
        When manual mode is disabled, returns empty dicts.
        If fields include 'value', 'min', 'max', they will be mapped accordingly.
        Otherwise, all non-bound fields will be put under 'params'.
        """
        if not self.use_manual_params.isChecked():
            return {"params": {}, "bounds": {}}
        df = self._collect_table_to_df()
        params: dict = {}
        bounds: dict = {}
        # Prefer common field names
        has_value = "value" in df.columns
        has_min = "min" in df.columns
        has_max = "max" in df.columns
        for pname, row in df.iterrows():
            if has_value:
                params[pname] = row.get("value")
            else:
                # If no explicit 'value', pick first column as the value
                if len(df.columns) > 0:
                    params[pname] = row.iloc[0]
            if has_min and has_max:
                min_v = row.get("min")
                max_v = row.get("max")
                # Only set bounds if both are present
                if pd.notna(min_v) and pd.notna(max_v):
                    try:
                        bounds[pname] = (float(min_v), float(max_v))
                    except Exception:
                        pass
        return {"params": params, "bounds": bounds}

    # --------------------------- Internal logic ----------------------------- #
    def _rebuild_table(self) -> None:
        # Block signals during rebuild
        self.table.blockSignals(True)
        try:
            # Define columns: first column is 'Parameter' (name), others are fields
            n_rows = len(self._param_names)
            n_cols = 1 + len(self._fields)
            self.table.clear()
            self.table.setRowCount(n_rows)
            self.table.setColumnCount(n_cols)

            headers = ["Parameter"] + self._fields
            self.table.setHorizontalHeaderLabels(headers)

            for r, pname in enumerate(self._param_names):
                # Name column (read-only)
                name_item = QTableWidgetItem(pname)
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self.table.setItem(r, 0, name_item)

                # Field value columns (editable depending on manual toggle)
                for c, field in enumerate(self._fields, start=1):
                    val = None
                    if (
                        self._df is not None
                        and pname in self._df.index
                        and field in self._df.columns
                    ):
                        val = self._df.loc[pname, field]
                    text = "" if pd.isna(val) else str(val)
                    item = QTableWidgetItem(text)
                    self.table.setItem(r, c, item)
        finally:
            self.table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        # Ignore programmatic changes when manual is disabled
        if not self.use_manual_params.isChecked():
            return
        self.parameters_changed.emit()

    def _collect_table_to_df(self) -> pd.DataFrame:
        # Build DataFrame from table contents
        rows = []
        for r in range(self.table.rowCount()):
            pname_item = self.table.item(r, 0)
            pname = pname_item.text() if pname_item else f"param_{r}"
            row_dict = {}
            for c, field in enumerate(self._fields, start=1):
                it = self.table.item(r, c)
                text = it.text() if it else ""
                row_dict[field] = self._coerce(text)
            rows.append((pname, row_dict))
        data = {name: vals for name, vals in rows}
        df = pd.DataFrame.from_dict(data, orient="index", columns=self._fields)
        return df

    @staticmethod
    def _coerce(text: str):
        # Try to coerce to int or float if possible; fallback to string
        if text is None or text == "":
            return None
        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except ValueError:
            return text

    def toggle_inputs(self):
        enabled = self.use_manual_params.isChecked()
        # Toggle editability of value cells based on manual mode.
        # We intentionally avoid calling `setEnabled` on the table so that
        # higher-level controllers remain responsible for widget enabled/disabled state.
        if enabled:
            self.table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        else:
            self.table.clearSelection()
            self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # No need to alter values on toggle; we just control interactivity.

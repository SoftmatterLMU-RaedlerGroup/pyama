"""
ParameterPanel rewritten to present parameters in a table instead of label+editor rows.
The table infers fields from an input pandas DataFrame and allows editing when
"Set parameters manually" is enabled.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import pandas as pd
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


# =============================================================================
# MAIN PARAMETER PANEL
# =============================================================================

class ParameterPanel(QWidget):
    """A widget that displays editable parameters in a table.

    Usage:
    - Use set_parameters_df(df) with a DataFrame of defaults.
      The DataFrame should have parameter names as index OR include a 'name' column.
      All other columns are treated as fields (e.g., value, min, max...).
    - Call get_values_df() to retrieve an updated DataFrame if manual mode is enabled.
    """

    # ------------------------------------------------------------------------
    # SIGNALS
    # ------------------------------------------------------------------------
    parameters_changed = Signal()

    # ------------------------------------------------------------------------
    # INITIALIZATION
    # ------------------------------------------------------------------------
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._initialize_state()
        self._build_ui()
        self._connect_signals()

    # ------------------------------------------------------------------------
    # STATE INITIALIZATION
    # ------------------------------------------------------------------------
    def _initialize_state(self) -> None:
        """Initialize internal state variables."""
        self._parameters_df: pd.DataFrame = pd.DataFrame()
        self._use_manual_params: bool = False

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)

        # Manual parameter checkbox
        self.use_manual_params = QCheckBox("Set parameters manually")
        layout.addWidget(self.use_manual_params)

        # Parameter table
        self.param_table = QTableWidget()
        self.param_table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self.param_table)

        # Configure table
        self._configure_table()

    def _configure_table(self) -> None:
        """Configure the parameter table appearance and behavior."""
        header = self.param_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.param_table.setAlternatingRowColors(True)
        self.param_table.verticalHeader().setVisible(False)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self.use_manual_params.toggled.connect(self._on_manual_mode_toggled)
        self.param_table.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    def _on_manual_mode_toggled(self, checked: bool) -> None:
        """Handle manual mode toggle changes."""
        self._use_manual_params = checked
        # Enable/disable table editing based on manual mode
        for row in range(self.param_table.rowCount()):
            for col in range(1, self.param_table.columnCount()):  # Skip name column
                item = self.param_table.item(row, col)
                if item:
                    if checked:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle table item changes."""
        # Ignore programmatic changes when manual is disabled
        if not self.use_manual_params.isChecked():
            return
        self.parameters_changed.emit()



    # ---------------------------- Public API -------------------------------- #

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

    def set_parameter(self, name: str, value) -> None:
        """Set the value of a single parameter by name.

        Only updates the parameter if manual mode is disabled, otherwise
        ignores the update to respect user's manual input.
        """
        # Don't update parameters when manual mode is enabled
        if self.use_manual_params.isChecked():
            return

        if self._df is None or name not in self._param_names:
            return

        # Find the row index for this parameter
        try:
            row_idx = self._param_names.index(name)
        except ValueError:
            return

        # Update the DataFrame if it exists
        if "value" in self._fields:
            self._df.loc[name, "value"] = value
        elif len(self._fields) > 0:
            # If no 'value' column, update the first field
            self._df.loc[name, self._fields[0]] = value

        # Update the table widget
        self.table.blockSignals(True)
        try:
            # Find the column for the value (prefer 'value' column, fallback to first field)
            col_idx = 1  # Default to first field column
            if "value" in self._fields:
                col_idx = self._fields.index("value") + 1

            item = self.table.item(row_idx, col_idx)
            if item is not None:
                item.setText(str(value))
        finally:
            self.table.blockSignals(False)

    def get_values_df(self) -> pd.DataFrame | None:
        """Return the current table as a DataFrame if manual mode is enabled; else None."""
        if not self.use_manual_params.isChecked():
            return None
        return self._collect_table_to_df()

    def _rebuild_table(self) -> None:
        """Rebuild the parameter table with current data."""
        # Block signals during rebuild
        self.param_table.blockSignals(True)
        try:
            # Define columns: first column is 'Parameter' (name), others are fields
            n_rows = len(self._param_names)
            n_cols = 1 + len(self._fields)
            self.param_table.clear()
            self.param_table.setRowCount(n_rows)
            self.param_table.setColumnCount(n_cols)

            headers = ["Parameter"] + self._fields
            self.param_table.setHorizontalHeaderLabels(headers)

            for r, pname in enumerate(self._param_names):
                # Name column (read-only)
                name_item = QTableWidgetItem(pname)
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self.param_table.setItem(r, 0, name_item)

                # Field value columns (editable depending on manual toggle)
                for c, field in enumerate(self._fields, start=1):
                    val = None
                    if (
                        self._parameters_df is not None
                        and pname in self._parameters_df.index
                        and field in self._parameters_df.columns
                    ):
                        val = self._parameters_df.loc[pname, field]
                    text = "" if pd.isna(val) else str(val)
                    item = QTableWidgetItem(text)
                    # Set editability based on manual mode
                    if self._use_manual_params:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self.param_table.setItem(r, c, item)
        finally:
            self.param_table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        # Ignore programmatic changes when manual is disabled
        if not self.use_manual_params.isChecked():
            return
        self.parameters_changed.emit()

    def _collect_table_to_df(self) -> pd.DataFrame:
        """Collect table data into a DataFrame."""
        # Build DataFrame from table contents
        rows = []
        for r in range(self.param_table.rowCount()):
            pname_item = self.param_table.item(r, 0)
            pname = pname_item.text() if pname_item else f"param_{r}"
            row_dict = {}
            for c, field in enumerate(self._fields, start=1):
                it = self.param_table.item(r, c)
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
            self.param_table.setEditTriggers(QTableWidget.EditTrigger.AllEditTriggers)
        else:
            self.param_table.clearSelection()
            self.param_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        # No need to alter values on toggle; we just control interactivity.

"""
ParameterPanel rewritten to present parameters in a table instead of label+editor rows.
The table uses a dict-based backend for simple parameter management.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import logging
from typing import Any
from PySide6.QtCore import Signal, Slot, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QHeaderView,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger(__name__)


# =============================================================================
# MAIN PARAMETER PANEL
# =============================================================================


class ParameterTable(QWidget):
    """A widget that displays editable parameters in a table.

    Usage:
    - Use set_parameters(params) with a dict of defaults.
      Format: {param_name: {field_name: value, ...}, ...}
      Example: {"fov_start": {"value": 0}, "background_weight": {"value": 0.0}}
    - Call get_values() to retrieve current values dict if manual mode is enabled.
      Returns: {param_name: {field_name: value, ...}, ...}
    - For backward compatibility, set_parameters_df(df) accepts pandas DataFrame.
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
        # Store as dict: {param_name: {field_name: value, ...}, ...}
        self._parameters: dict[str, dict[str, Any]] = {}
        self._param_names: list[str] = []
        self._fields: list[str] = []

    # ------------------------------------------------------------------------
    # UI CONSTRUCTION
    # ------------------------------------------------------------------------
    def _build_ui(self) -> None:
        """Build the user interface layout."""
        layout = QVBoxLayout(self)

        # Manual parameter checkbox (unchecked by default)
        self._use_manual_params = QCheckBox("Set parameters manually")
        self._use_manual_params.setChecked(False)  # Ensure unchecked by default
        layout.addWidget(self._use_manual_params)

        # Parameter table (initially hidden until parameters are set)
        self._param_table = QTableWidget()
        self._param_table.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        self._param_table.setVisible(False)  # Initially hidden
        layout.addWidget(self._param_table)

        # Configure table
        self._configure_table()

        # Initialize table to non-editable state (manual params unchecked)
        self._toggle_table_editability(False)

    def _configure_table(self) -> None:
        """Configure the parameter table appearance and behavior."""
        header = self._param_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._param_table.setAlternatingRowColors(True)
        self._param_table.verticalHeader().setVisible(False)

    def _toggle_table_editability(self, enabled: bool) -> None:
        """Toggle table editability based on manual parameter setting."""
        self._param_table.blockSignals(True)
        try:
            for row in range(self._param_table.rowCount()):
                for col in range(
                    1, self._param_table.columnCount()
                ):  # Skip name column
                    item = self._param_table.item(row, col)
                    if item:
                        if enabled:
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                        else:
                            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        finally:
            self._param_table.blockSignals(False)

    # ------------------------------------------------------------------------
    # SIGNAL CONNECTIONS
    # ------------------------------------------------------------------------
    def _connect_signals(self) -> None:
        """Connect UI widget signals to handlers."""
        self._use_manual_params.toggled.connect(self._on_manual_mode_toggled)
        self._param_table.itemChanged.connect(self._on_item_changed)

    # ------------------------------------------------------------------------
    # EVENT HANDLERS
    # ------------------------------------------------------------------------
    @Slot(bool)
    def _on_manual_mode_toggled(self, checked: bool) -> None:
        """Handle manual mode toggle changes."""
        # Table visibility logic:
        # - When manual mode is CHECKED: show table (so user can edit values)
        # - When manual mode is UNCHECKED: hide table (so users see defaults, not an empty table)
        should_show_table = checked

        self._param_table.setVisible(should_show_table)

        if should_show_table:
            # Make table editable only if manual mode is enabled
            self._toggle_table_editability(checked)

    # ---------------------------- Public API -------------------------------- #

    def set_parameters(self, params: dict[str, dict[str, Any]]) -> None:
        """Initialize the table from a dict of parameters.

        Args:
            params: Dict mapping parameter names to field dicts.
                    Format: {param_name: {field_name: value, ...}, ...}
                    Example: {"fov_start": {"value": 0}, "background_weight": {"value": 0.0}}
        """
        if not params:
            # Clear the table
            self._parameters = {}
            self._fields = []
            self._param_names = []
            self._rebuild_table()
            return

        # Normalize parameter names to strings
        self._parameters = {str(name): {str(f): v for f, v in fields.items()} 
                           for name, fields in params.items()}
        self._param_names = list(self._parameters.keys())
        
        # Collect all unique field names across all parameters
        all_fields = set()
        for fields_dict in self._parameters.values():
            all_fields.update(fields_dict.keys())
        self._fields = sorted(all_fields)

        self._rebuild_table()

    def set_parameters_df(self, df) -> None:
        """Initialize the table from a pandas DataFrame (backward compatibility).

        - If a 'name' column exists, it is used as the row index and not shown as a field.
        - Otherwise, the DataFrame's index is used for parameter names.
        - All remaining columns are fields.
        """
        if df is None or df.empty:
            self.set_parameters({})
            return

        df_local = df.copy()
        if "name" in df_local.columns:
            df_local = df_local.set_index("name")
        # Normalize index to strings
        df_local.index = df_local.index.map(lambda x: str(x))

        # Convert DataFrame to dict format
        params = {}
        for param_name in df_local.index:
            params[str(param_name)] = {
                field: df_local.loc[param_name, field]
                for field in df_local.columns
            }
        
        self.set_parameters(params)

    def get_values(self) -> dict[str, dict[str, Any]] | None:
        """Return the current table as a dict if manual mode is enabled; else None.
        
        Returns:
            Dict mapping parameter names to field dicts.
            Format: {param_name: {field_name: value, ...}, ...}
        """
        if not self._use_manual_params.isChecked():
            return None
        return self._collect_table_to_dict()

    def get_values_df(self):
        """Return the current table as a DataFrame if manual mode is enabled (backward compatibility)."""
        try:
            import pandas as pd
        except ImportError:
            logger.warning("pandas not available, returning dict instead")
            return self.get_values()
        
        values_dict = self.get_values()
        if values_dict is None:
            return None
        
        # Convert dict to DataFrame
        return pd.DataFrame.from_dict(values_dict, orient="index", columns=self._fields)

    def is_manual_mode(self) -> bool:
        """Return whether manual parameter mode is enabled."""
        return self._use_manual_params.isChecked()

    def _rebuild_table(self) -> None:
        """Rebuild the parameter table with current data."""
        # Block signals during rebuild
        self._param_table.blockSignals(True)
        try:
            # Define columns: first column is 'Parameter' (name), others are fields
            n_rows = len(self._param_names)
            n_cols = 1 + len(self._fields)
            self._param_table.clear()
            self._param_table.setRowCount(n_rows)
            self._param_table.setColumnCount(n_cols)

            headers = ["Parameter"] + self._fields
            self._param_table.setHorizontalHeaderLabels(headers)

            for r, pname in enumerate(self._param_names):
                # Name column (read-only)
                name_item = QTableWidgetItem(pname)
                name_item.setFlags(
                    Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                )
                self._param_table.setItem(r, 0, name_item)

                # Field value columns (editable depending on manual toggle)
                for c, field in enumerate(self._fields, start=1):
                    val = None
                    if (
                        pname in self._parameters
                        and field in self._parameters[pname]
                    ):
                        val = self._parameters[pname][field]
                    # Format display: show integers without decimal places
                    if val is None:
                        text = ""
                    elif isinstance(val, int):
                        text = str(val)
                    elif isinstance(val, float) and val.is_integer():
                        text = str(int(val))
                    else:
                        text = str(val)
                    item = QTableWidgetItem(text)
                    # Set editability based on manual mode
                    if self._use_manual_params:
                        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                    else:
                        item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                    self._param_table.setItem(r, c, item)
        finally:
            self._param_table.blockSignals(False)

    def _on_item_changed(self, item: QTableWidgetItem):
        """Handle table item changes."""
        # Only emit signals if manual mode is enabled
        if not self._use_manual_params:
            return

        # Log the value change
        row = item.row()
        col = item.column()
        param_name = ""
        field_name = ""
        new_value = item.text()

        # Get parameter name from first column
        if row < self._param_table.rowCount():
            name_item = self._param_table.item(row, 0)
            if name_item:
                param_name = name_item.text()

        # Get field name from column header
        if col > 0 and col <= len(self._fields):
            field_name = self._fields[col - 1]

        logger.debug(
            "Parameter table value changed: %s.%s = %s (row=%d, col=%d)",
            param_name,
            field_name,
            new_value,
            row,
            col,
        )

        self.parameters_changed.emit()

    def _collect_table_to_dict(self) -> dict[str, dict[str, Any]]:
        """Collect table data into a dict."""
        # Build dict from table contents
        params = {}
        for r in range(self._param_table.rowCount()):
            pname_item = self._param_table.item(r, 0)
            pname = pname_item.text() if pname_item else f"param_{r}"
            param_dict = {}
            for c, field in enumerate(self._fields, start=1):
                it = self._param_table.item(r, c)
                text = it.text() if it else ""
                param_dict[field] = self._coerce(text)
            params[pname] = param_dict
        return params

    @staticmethod
    def _coerce(text: str):
        """Try to coerce to int or float if possible; fallback to string."""
        if text is None or text == "":
            return None
        try:
            if text.isdigit() or (text.startswith("-") and text[1:].isdigit()):
                return int(text)
            return float(text)
        except ValueError:
            return text

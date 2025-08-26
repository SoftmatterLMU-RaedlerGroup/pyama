'''
Reusable ParameterPanel widget for dynamically creating parameter editing forms.
'''

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
    QComboBox,
    QLabel,
    QCheckBox,
)
from PySide6.QtCore import Signal


class ParameterPanel(QWidget):
    """A widget that dynamically creates a form based on parameter definitions."""

    parameters_changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QVBoxLayout(self)
        self.form_layout = QFormLayout()
        self.main_layout.addLayout(self.form_layout)
        
        self.param_widgets = {}
        self.bounds_widgets = {}
        self.param_defaults = {}

        self.use_manual_params = QCheckBox("Set parameters manually")
        self.use_manual_params.stateChanged.connect(self.toggle_inputs)
        self.main_layout.insertWidget(0, self.use_manual_params)

    def set_parameters(self, param_definitions: list[dict]):
        """Create the parameter form based on a list of definitions."""
        while self.form_layout.count():
            item = self.form_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.param_widgets.clear()
        self.bounds_widgets.clear()
        self.param_defaults.clear()

        for param_def in param_definitions:
            param_name = param_def.get("name")
            self.param_defaults[param_name] = {
                "default": param_def.get("default"),
                "min": param_def.get("min"),
                "max": param_def.get("max"),
            }

            param_type = param_def.get("type")
            label = param_def.get("label", param_name)
            widget = None

            if param_type == "int":
                widget = QSpinBox()
            elif param_type == "float":
                widget = QDoubleSpinBox()
                widget.setDecimals(6)
            elif param_type == "enum":
                widget = QComboBox()
                if "choices" in param_def:
                    widget.addItems(param_def["choices"])
            elif param_type == "str":
                widget = QLineEdit()

            if widget:
                if isinstance(widget, (QSpinBox, QDoubleSpinBox)):
                    if "min" in param_def: widget.setMinimum(param_def["min"])
                    if "max" in param_def: widget.setMaximum(param_def["max"])
                    widget.valueChanged.connect(lambda: self.parameters_changed.emit())
                elif isinstance(widget, QComboBox):
                    widget.currentTextChanged.connect(lambda: self.parameters_changed.emit())
                else:
                    widget.textChanged.connect(lambda: self.parameters_changed.emit())

                container = QWidget()
                h_layout = QHBoxLayout(container)
                h_layout.setContentsMargins(0, 0, 0, 0)
                h_layout.addWidget(widget)

                if param_def.get("show_bounds"):
                    min_bound = QLineEdit()
                    max_bound = QLineEdit()
                    h_layout.addWidget(QLabel("Bounds:"))
                    h_layout.addWidget(min_bound)
                    h_layout.addWidget(QLabel("-"))
                    h_layout.addWidget(max_bound)
                    self.bounds_widgets[param_name] = (min_bound, max_bound)

                self.form_layout.addRow(QLabel(label), container)
                self.param_widgets[param_name] = (param_type, widget)
        
        self.toggle_inputs()

    def get_values(self) -> dict:
        values = {"params": {}, "bounds": {}}
        
        # Only return parameter values if manual mode is enabled
        if self.use_manual_params.isChecked():
            for name, (param_type, widget) in self.param_widgets.items():
                if param_type in ["int", "float"]:
                    values["params"][name] = widget.value()
                elif param_type == "enum":
                    values["params"][name] = widget.currentText()
                elif param_type == "str":
                    values["params"][name] = widget.text()

            for name, (min_w, max_w) in self.bounds_widgets.items():
                min_val_str = min_w.text()
                max_val_str = max_w.text()
                if min_val_str and max_val_str:
                    try:
                        values["bounds"][name] = (float(min_val_str), float(max_val_str))
                    except ValueError:
                        pass # Or handle error
        
        # Return empty dicts when manual mode is disabled - this tells fitting to use automatic estimation
        return values

    def toggle_inputs(self):
        enabled = self.use_manual_params.isChecked()
        for name, (param_type, widget) in self.param_widgets.items():
            widget.setEnabled(enabled)
            if enabled:
                defaults = self.param_defaults.get(name, {})
                if param_type in ["int", "float"]:
                    widget.setValue(defaults.get("default", 0))
                elif param_type == "enum":
                    widget.setCurrentText(str(defaults.get("default", "")))
                elif param_type == "str":
                    widget.setText(str(defaults.get("default", "")))

                if name in self.bounds_widgets:
                    min_w, max_w = self.bounds_widgets[name]
                    min_w.setText(str(defaults.get("min", "")))
                    max_w.setText(str(defaults.get("max", "")))
            else:
                if not isinstance(widget, QComboBox):
                    widget.clear()
                if name in self.bounds_widgets:
                    min_w, max_w = self.bounds_widgets[name]
                    min_w.clear()
                    max_w.clear()

        for min_w, max_w in self.bounds_widgets.values():
            min_w.setEnabled(enabled)
            max_w.setEnabled(enabled)
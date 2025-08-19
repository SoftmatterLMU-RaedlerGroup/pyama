# Cell Kinetics Batch Fitting GUI – PySide6 Layout

A three-panel horizontal layout for high-throughput kinetic fitting and QC.

---

| LEFT PANEL           | MIDDLE PANEL (Controls)         | RIGHT PANEL                |
| -------------------- | ------------------------------- | -------------------------- |
| [Load CSV]           | [Fitting Parameter Group]       | [Fitting Quality Plot]     |
| [All Sequences Plot] | p1 [ ] p2 [ ]                   | [Parameter Histogram Plot] |
| (gray/all, red avg)  | p3 [ ] p4 [ ]                   | [Dropdown: parameter]      |
|                      | [Start Batch Fitting]           |                            |
|                      | [QC: cell_id/Visualize/Shuffle] |                            |

---

## | Status Bar (progress/messages) |

Widget mapping:

- Left Panel (QVBoxLayout):

  - QPushButton "Load CSV"
  - FigureCanvasQTAgg or Plotly: plot all time sequences (gray, low alpha); overlay average in red

- Middle Panel (QVBoxLayout):

  - QGroupBox "Fitting Parameters" (QFormLayout):
    - QDoubleSpinBox or QLineEdit for each parameter (p1, p2, p3, p4)
  - QPushButton "Start Batch Fitting"
  - QGroupBox "Quality Control":
    - QLineEdit for cell_id
    - QPushButton "Visualize"
    - QPushButton "Shuffle"

- Right Panel (QVBoxLayout):

  - FigureCanvasQTAgg or Plotly: Fitting Quality Plot (e.g., histogram/scatter of RMSE)
  - QComboBox: Select fit parameter for histogram
  - FigureCanvasQTAgg or Plotly: Parameter Histogram

- Application uses QSplitter(Qt.Horizontal) to lay out panels
- QStatusBar for message/progress

# Minimal PySide6 Main Structure, Pseudocode

QMainWindow
|
|** QSplitter(Qt.Horizontal)
| |** left_panel (QWidget/VBox): load_button, all_seq_plot
| |** middle_panel (QWidget/VBox): param_group, start_btn, qc_group
| |** right_panel (QWidget/VBox): fit_quality_plot, param_dropdown, param_hist
|
|\_\_ QStatusBar

# Core Flow

- User loads CSV (LEFT)
- All-sequences plot updates (LEFT)
- User sets initial parameters (MIDDLE)
- User clicks Start Batch Fitting (MIDDLE)
- Fitting stats/diagnostics appear (RIGHT)
- User can QC with cell_id, shuffle, and visualize (MIDDLE)

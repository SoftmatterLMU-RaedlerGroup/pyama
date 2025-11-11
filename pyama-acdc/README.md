# PyAMA ↔ Cell-ACDC plugin

`pyama-acdc` exposes a tiny API that Cell-ACDC can use (optionally) to surface
PyAMA workflow helpers inside its Qt welcome window and to launch the workflow
dialog just like SpotMAX.

## Features

- Exposes `pyama_acdc.icon_path` and `pyama_acdc.logo_path` so the launcher can
  show PyAMA in the main window modules list.
- Provides `pyama_acdc._run.run_gui(...)`, mirroring SpotMAX's integration, so
  Cell-ACDC can open the workflow dialog as a managed window.
- The workflow dialog lays out PyAMA-specific ordering:
  - **Step 0** calls Cell-ACDC's native "Create data structure" dialog
  - **Step 1** launches the segmentation module directly (PyAMA runs segmentation
    right after structuring data)
  - **Step 2** launches the data prep module
  - **Step 3** launches the main GUI for measurements

## Usage inside Cell-ACDC

```python
from pyama_acdc import pyAMA_Win


class mainWin(QMainWindow):
    def showPyamaWorkflow(self):
        win = pyAMA_Win(self)
        win.show()
```

Alternatively, import `pyama_acdc._run.run_gui` and launch it directly (just
like Cell-ACDC's main window does for SpotMAX).

## Development

The package ships as part of the PyAMA workspace but is published separately.
Install with:

```bash
uv pip install -e pyama-acdc/
```

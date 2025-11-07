# PyAMA ↔ Cell-ACDC plugin

`pyama-acdc` exposes a tiny API that Cell-ACDC can use (optionally) to surface
PyAMA workflow helpers inside its Qt welcome window.

## Features

- Adds a new **Utilities → PyAMA Workflow...** menu action when the plugin is
  installed.
- Clicking the action opens a non-modal dialog with PyAMA-specific ordering:
  - **Step 0** calls Cell-ACDC's native "Create data structure" dialog
  - **Step 1** launches the segmentation module directly (PyAMA runs segmentation
    right after structuring data)
  - **Step 2** launches the data prep module
  - **Step 3** is reserved for the upcoming measurement-configuration module

## Usage inside Cell-ACDC

```python
from pyama_acdc import add_pyama_workflow_action


class mainWin(QMainWindow):
    def createMenuBar(self):
        super().createMenuBar()
        add_pyama_workflow_action(self)
```

The helper looks for `self.utilsMenu` by default, but you can explicitly pass a
different `QMenu` via the `menu=` keyword if needed.

## Development

The package ships as part of the PyAMA workspace but is published separately.
Install with:

```bash
uv pip install -e pyama-acdc/
```

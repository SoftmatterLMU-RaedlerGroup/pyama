# PyAMA-Qt Code Analysis

## Core Functions in old/ Directory

### 1. Binarize Functions

**Primary Implementation:**
- `old/src/pyama/tools/binarize.py:10` - `binarize_phasecontrast_stack()` - Main function for binarizing entire phase-contrast image stacks
- `old/src/pyama/img_op/coarse_binarize_phc.py:56` - `binarize_frame()` - Core binarization algorithm using logarithmic standard deviation filtering and morphological operations

**GUI Integration:**
- Menu item: "Binarize…" in Tools menu (`old/src/pyama/session/view_tk.py:145`)
- Callback: `binarize()` method (`old/src/pyama/session/view_tk.py:1033`)
- Dynamically enabled/disabled based on phase-contrast channel availability

### 2. Pickle Maximum Bounding Box Function

**Implementation:**
- `old/src/pyama/tools/roi_bboxer.py:4` - `get_selected_bboxes()` - Core function that calculates and pickles maximum bounding boxes for selected cells
- `old/src/pyama/session/view_tk.py:1078` - `_pickle_max_bbox()` - GUI wrapper method

**GUI Integration:**
- Menu item: "Pickle maximum bounding box" in Tools menu (`old/src/pyama/session/view_tk.py:146`)
- Exports maximum spatial extent of each cell across all frames to pickle file

### 3. Background Correction Functions

**Implementation:**
- `old/src/pyama/img_op/background_correction.py:87` - `background_schwarzfischer()` - Schwarzfischer et al. background correction algorithm for fluorescence images
- `old/src/pyama/tools/bgcorr.py:10` - `perform_background_correction()` - High-level wrapper function

**GUI Integration:**
- Menu item: "Background correction…" in Tools menu (`old/src/pyama/session/view_tk.py:147`)
- Callback: `_background_correction()` method (`old/src/pyama/session/view_tk.py:1054`)

## GUI Architecture

All functions are accessible through the **Tools menu** in the main tkinter application (`old/src/pyama/session/view_tk.py`). The GUI uses an event-driven architecture where menu callbacks open file dialogs and fire events to a control queue for processing by the controller.

**Menu Structure:**
```python
# Tools menu creation (lines 125-147)
self.toolmenu = tk.Menu(menubar)
menubar.add_cascade(label="Tools", menu=self.toolmenu)
self.toolmenu.add_command(label="Binarize…", command=self.binarize, state=tk.DISABLED)
self.toolmenu.add_command(label="Pickle maximum bounding box", command=self._pickle_max_bbox)
self.toolmenu.add_command(label="Background correction…", command=self._background_correction)
```
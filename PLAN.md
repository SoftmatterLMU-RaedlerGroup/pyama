# Trace visualization plan
## Goal

Add trace visualization alongside the existing image viewer. Step 1 (GUI skeleton with `TraceViewer`) is done. Next, wire data and overlay logic.

## Milestones

- [x] Step 1: Add `TraceViewer` GUI (plot placeholder + checkable list) and integrate via splitter
- [x] Step 1.5: Implement mock plotting with 10 synthetic traces; selection-driven plotting
- [x] Step 1.6: Replace list with table; add header-click to toggle all/none; add active-trace highlight (red)
- [x] Step 2: Load traces CSV for current FOV and populate `TraceViewer` (limit to first 10 trace IDs)
- [ ] Step 3: Overlay cell markers in `ImageViewer` (red for selected, blue for unselected)
- [x] Step 4: Plot selected traces in `TraceViewer` (using real data)
- [ ] Step 5: Performance/UX polish (throttle redraws, handle large trace sets)
- [ ] Step 6: Tests and brief docs

## Data discovery and loading (Step 2)

- On FOV load complete, find the traces CSV for that FOV: `..._fovXXXX_traces.csv`.
- Parse with pandas and build structures:
  - `all_trace_ids`: unique `cell_id` values (as strings), limited to first 10 for now
  - `frames`: 0..max(`frame`) from the CSV
  - `series_by_id`: map `cell_id` -> series aligned to `frames` using intensity column (prefers `intensity_total`, then `mean_intensity`, then `fl_int_mean`); use NaN where missing
  - `frame_index_to_cells` (for overlays, later): `dict[int, list[{cell_id, x, y}]]`, derived from rows with `centroid_x`, `centroid_y`
- If no CSV exists, clear/disable `TraceViewer`.

## Wire TraceViewer to project (Step 2)

- When FOV data is ready, populate via `trace_viewer.set_trace_data(all_trace_ids, frames, series_by_id)`; table shows first 10 IDs.
- Connect `trace_viewer.selection_changed` to a handler that updates selected trace IDs and triggers an image redraw (overlay wiring pending in Step 3).
- Optional: connect a signal for active trace ID (or query `trace_viewer._active_trace_id`) to highlight overlays.

## Saving inspection labels (Step 2.7)

- `TraceViewer` provides a Save button under the table to write a new CSV ending with `_inspected.csv` alongside the source traces CSV.
- Adds/overwrites a boolean `good` column: `True` for checked `Trace ID`s, `False` otherwise (match by `cell_id`).

## Image overlay in ImageViewer (Step 3)

- Maintain state for current FOV:
  - `available_trace_ids`, `selected_trace_ids`
  - `frame_index_to_cells`
- On frame change or selection change, redraw overlays:
  - Compute scale/offset from array size to label pixmap (keep aspect ratio)
  - For each cell in the current frame, draw a circle with QPainter:
    - Red if its `cell_id` is selected
    - Blue otherwise

## Signal wiring (Step 2–3)

- After worker signals FOV ready, load traces CSV and set trace IDs.
- Connect:
  - `TraceViewer.selection_changed -> ImageViewer.set_selected_traces(...)`
  - Frame navigation in `ImageViewer` triggers overlay redraw automatically

## Plotting traces (Step 4)

- In `TraceViewer`, on `selection_changed`, plot the selected time series on the top canvas (using CSV data).
- Active trace (clicked `Trace ID` cell among checked rows) is highlighted in red; others in black.
- Keep plotting lightweight; clear and re-plot selected lines only.

## Edge cases (Step 2–5)

- No traces: disable `TraceViewer`, no overlays.
- Large number of traces: keep drawing lightweight (thin pens, avoid heavy alpha blending loops), consider downsampling for plotting.
- Missing frames per cell: if a cell doesn’t exist in a frame, skip drawing.

## Shared cache compatibility

- Image data remains in the shared cache for the current FOV only; cache is cleared on FOV switch before loading and starting the worker. Overlays are drawn at display time and do not modify cached arrays.

## Acceptance criteria

- Right panel shows trace table with a checkbox column and a plot area (done).
- Header click on the checkbox column toggles all/none (done).
- Clicking a checked `Trace ID` highlights that trace in red in the plot (done).
- Loading a FOV with traces populates the table with up to 10 `Trace ID`s (done).
- As the user flips frames, cells are circled: red for selected, blue for unselected.
- Selecting/deselecting traces updates the image overlays immediately.
- No crashes when traces are missing.
- Save button writes an inspected CSV (`*_inspected.csv`) with a boolean `good` column matching checked rows (done).


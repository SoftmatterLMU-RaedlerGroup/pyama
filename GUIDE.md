# Processing Tab Quick Guide

1. Launch PyAMA-Pro and switch to Processing.
2. Browse for the ND2 file so metadata and channel lists populate.
3. Pick the phase contrast channel and toggle only the shape features you need.
4. For each fluorescence channel, select a feature and press Add to queue it.
5. Choose a save directory with room for YAML, traces, and diagnostic assets.
6. Enable manual parameters to expose how many FOVs run, which indices are included, and how aggressively to parallelize.
7. `batch_size` governs how many FOVs move through the pipeline together; start at 1-2 for quick validation, then raise once results look good.
8. `n_workers` is the number of worker threads; match it to available CPU cores and memory so segmentation and tracking stay stable.
9. `background_weight` clamps to 0-1 where 0 keeps raw fluorescence, 1 subtracts full background, and mid values mix the two.
10. Click Start Complete Workflow; watch the status banner for each stage.
11. Cancel stops new batches while letting running workers finish safely.
12. Use Assign FOVs to map ranges like 0-3,5-7 onto descriptive sample names.
13. Save the assignment table to YAML so merges and CLI runs stay in sync.
14. Load the samples YAML plus processing_results.yaml in the Merge section.
15. Select an output folder (often the processing folder) for merged CSVs.
16. Run Merge to immediately build one CSV per sample.
17. After the workflow, note the summary message pointing to output paths.
18. Expect processing_results.yaml, per-FOV trace CSVs, and masks in the save folder.

# Visualization Tab Quick Guide

1. Switch to Visualization once processing output exists (YAML plus traces).
2. Click Load Folder and target the same save directory used in Processing.
3. Confirm the header shows project stats like total FOVs and detected channels.
4. Use the FOV spinbox to pick a field; small jumps make it easier to compare neighbors.
5. Multiselect relevant channels (e.g., pc, seg_labeled, fl_background) before rendering.
6. Choose the Feature dropdown for trace plotting; defaults to intensity_total.
7. Press Start Visualization and wait for the semantic message “Visualization finished.”
8. Navigation buttons let you step ±1 frame or ±10 frames for quick scans.
9. The Data Type dropdown switches between raw, segmentation, and background layers.
10. Click trace IDs below the plot to highlight them; red indicates the active trace.
11. Right-click a trace to toggle its quality flag between good and bad.
12. Bad traces hide from the chart but stay listed for record keeping.
13. Pagination controls walk through trace batches per FOV; note the badge count.
14. Selected traces add a red centroid marker atop the image to confirm location.
15. Use the context tooltip to read frame number and timestamp when hovering.
16. When satisfied, click Save Inspected CSV to generate a `_inspected` copy.
17. Reloading the same folder auto-detects inspected files so QC states persist.
18. Keep visualization folders organized; separate channels or QC stages into subfolders if needed.

# Analysis Tab Quick Guide

1. Load the merged or inspected CSV via Load CSV; the overview chart updates instantly.
2. Optionally load fitted results to compare against prior work or resume analysis.
3. Pick a model (trivial, maturation, etc.); defaults populate the parameter table.
4. Enable manual parameters when you want to tweak bounds or initial guesses.
5. Parameters display lower/upper limits plus current value; keep them physically meaningful.
6. Use the Good Fits Only toggle in the quality panel to focus on R² > 0.9 data.
7. Click Start Fitting to spawn the worker thread; watch for “Fitting started” status.
8. The progress bar advances per batch of traces so long runs feel responsive.
9. When fitting finishes, results save automatically with a `_fitted` suffix in the CSV name.
10. The left plot overlays raw traces (blue) and fitted curves (red) for selected cells.
11. Quality statistics show Good/Mid/Bad percentages; use them to judge parameter choices.
12. Navigate the trace list by FOV; Previous/Next buttons cycle through groups.
13. Selecting a trace updates the curve plot and the textual metadata beneath it.
14. Use the Parameter Analysis panel to view histograms of any fitted parameter.
15. Switch to scatter mode to study correlations (choose X and Y parameters separately).
16. Apply the good-fit filter in the histogram view to clean outliers before exporting figures.
17. Save All Plots exports PNGs of the histograms and scatter plots for lab notebooks.
18. If a fit fails, inspect the log message, adjust bounds or initial values, and rerun.

# PyAMA Testing Protocol

This document provides step-by-step testing protocols for validating PyAMA functionality. Copy each section and perform tests sequentially, checking items as you complete them.

## PyAMA-Qt GUI Testing Protocol

### Setup Prerequisites

- [ ] PyAMA installed and dependencies available (`uv sync --all-extras`)
- [ ] Test ND2 file available with phase contrast and fluorescence channels
- [ ] Output directory prepared for test results

### Processing Tab Tests

#### Workflow Execution

##### Initial Setup

- [ ] Launch PyAMA-Qt with `uv run pyama-qt --debug`
- [ ] Navigate to Processing tab
- [ ] Click "Browse" button next to "Microscopy File:" and choose test ND2 file
- [ ] Verify status bar shows "xxx loaded successfully" (where xxx is the filename)

##### Channel Configuration

- [ ] In the Channels section, select phase contrast channel from dropdown
- [ ] In "Phase Contrast Features" list, select desired features (multi-select enabled)
- [ ] In "Fluorescence" section, select wrong channel from dropdown
- [ ] Select wrong feature from feature dropdown and click "Add" button
- [ ] In "Fluorescence Features" list, select the wrong entry and click "Remove Selected"
- [ ] Select correct fluorescence channel and feature, then click "Add"

##### Output Configuration

- [ ] Click "Browse" button next to "Save Directory:" and select output folder

##### Default Workflow Test

- [ ] Click "Start Complete Workflow" button
- [ ] Verify progress bar appears and "Cancel" button becomes enabled
- [ ] Press "Cancel" button during workflow execution
- [ ] Verify workflow stops and status shows "Workflow cancelled"

##### Manual Parameter Configuration

- [ ] Check "Set parameters manually" checkbox - parameter table should become visible
- [ ] Verify fov_start shows 0 and fov_end shows n_fov-1 (where n_fov is total number of FOVs from metadata)
- [ ] Change fov_end value to 1 in the parameter table

##### Complete Workflow Execution

- [ ] Click "Start Complete Workflow" button
- [ ] Verify progress bar appears and "Cancel" button becomes enabled
- [ ] Press "Cancel" button during workflow execution (copying/segmentation/correction/tracking/extraction phases)
- [ ] Verify workflow stops and status shows "Workflow cancelled"
- [ ] Check output folder - all fov_XXX directories should be removed/cleaned up
- [ ] Click "Start Complete Workflow" again and let it complete
- [ ] Verify progress bar updates and status messages appear during processing
- [ ] Confirm workflow completes with "Results saved to [output directory]" message
- [ ] Check output directory for processing_results.yaml and fov_XXX directories with NPY files

#### Merge Functionality

- [ ] After workflow completion, click "Merge Results"
- [ ] Verify merge dialog opens with available results
- [ ] Select results to merge and confirm
- [ ] Check that merged CSV is created in output directory
- [ ] Verify merged CSV contains expected columns and data

### Visualization Tab Tests

#### Data Loading

- [ ] Navigate to Visualization tab
- [ ] Click "Load Phase Contrast" and select corrected phase data
- [ ] Verify phase contrast images display in viewer
- [ ] Test navigation between frames/time points
- [ ] Click "Load Fluorescence" and select corrected fluorescence data
- [ ] Verify fluorescence images display correctly
- [ ] Test channel switching between phase and fluorescence

#### Trace Inspection

- [ ] Click "Load Traces" and select merged traces CSV
- [ ] Verify traces appear as overlays on images
- [ ] Click on individual traces to select/highlight them
- [ ] Inspect trace information panel shows correct data
- [ ] Test deselecting traces (click to deselect)
- [ ] Select multiple traces for inspection
- [ ] Verify trace colors and visibility are clear

#### Save Inspected Data

- [ ] After inspecting and selecting/deselecting traces, click "Save Inspected"
- [ ] Choose output location and filename
- [ ] Verify saved CSV contains only selected traces
- [ ] Confirm file structure matches expected format

### Analysis Tab Tests

#### Model Selection and Fitting

- [ ] Navigate to Analysis tab
- [ ] Click "Load Traces" and select inspected traces CSV
- [ ] Choose "Trivial" model from model dropdown
- [ ] Configure fitting parameters (use defaults)
- [ ] Click "Fit Model" to start analysis
- [ ] Verify fitting progress and completion
- [ ] Repeat with "Maturation" model
- [ ] Compare results between models

#### Results Visualization

- [ ] After fitting completes, click "Show Random Traces"
- [ ] Verify random sample of fitted traces displays
- [ ] Check that fitted curves overlay raw data correctly
- [ ] Test parameter analysis visualization
- [ ] Verify parameter distributions and correlations display
- [ ] Navigate through different parameter views

#### Export Results

- [ ] Click "Save All Plots"
- [ ] Choose output directory for plots
- [ ] Verify all analysis plots are saved (PNG/SVG)
- [ ] Check parameter analysis files are exported
- [ ] Confirm fitted parameters CSV is created
- [ ] Verify export includes model metadata and fit statistics

### Cross-Tab Integration Tests

#### Data Flow Validation

- [ ] Process data in Processing tab → Verify available in Visualization
- [ ] Inspect traces in Visualization → Save and load in Analysis
- [ ] Analyze results in Analysis → Verify plots can be exported
- [ ] Test switching between tabs preserves loaded data
- [ ] Verify status messages update correctly across tabs

#### Error Handling

- [ ] Try loading incompatible file formats
- [ ] Test processing with missing parameters
- [ ] Verify graceful handling of corrupted files
- [ ] Check error messages are informative and user-friendly

### Performance Tests

#### Large Dataset Handling

- [ ] Test with multi-FOV dataset (if available)
- [ ] Verify UI remains responsive during processing
- [ ] Check memory usage with large datasets
- [ ] Test navigation through many frames/time points
- [ ] Verify trace rendering performance with many cells

### User Experience Tests

#### Interface Consistency

- [ ] Verify all buttons have tooltips
- [ ] Check keyboard shortcuts work as expected
- [ ] Test window resizing and layout adaptation
- [ ] Verify dialogs are properly sized and centered
- [ ] Check status bar updates are timely and informative

#### Workflow Intuitiveness

- [ ] Test complete workflow without documentation
- [ ] Verify navigation flow is logical (Processing → Visualization → Analysis)
- [ ] Check that required actions are clearly indicated
- [ ] Verify progress indicators for long operations
- [ ] Test undo/redo functionality where applicable

## Test Results Summary

### Passed Tests: [ ]/[ ]

### Failed Tests: [ ]/[ ]

### Issues Found

1.
2.
3.

### Recommendations

1.
2.
3.

---

**Notes for Testers:**

- Each checkbox should be ticked only after completing the specific test
- Document any issues with specific steps, error messages, or unexpected behavior
- Include system information (OS, Python version, dependencies) for bug reports
- Take screenshots of any UI issues or unexpected behavior
- Test with different ND2 files if possible to validate robustness

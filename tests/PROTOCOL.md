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

- [ ] Launch PyAMA-Qt with `uv run pyama-pro --debug`
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

#### Project Loading

##### Initial Setup

- [ ] Navigate to Visualization tab
- [ ] Click "Load Folder" button and select processing results directory
- [ ] Verify status bar shows "X FOVs loaded from [directory]" (where X is number of FOVs)
- [ ] Check project details text shows correct FOV count and available data types
- [ ] Verify channel list becomes visible with available channels

##### Channel Selection

- [ ] In "Visualization Settings" section, verify FOV spinbox shows range (0 to max_fov-1)
- [ ] Select multiple channels from the channel list (multi-select enabled)
- [ ] Verify "Start Visualization" button becomes enabled when channels are selected
- [ ] Deselect all channels and verify button becomes disabled
- [ ] Select channels again and proceed to visualization

#### Visualization Execution

##### Default Visualization Test

- [ ] Click "Start Visualization" button
- [ ] Verify progress bar appears and shows "Loading visualization data..."
- [ ] Confirm visualization completes with "FOV loaded successfully" message
- [ ] Check image viewer displays selected channels in data type dropdown
- [ ] Verify frame navigation controls work (<<, <, >, >>)
- [ ] Test frame label updates correctly (Frame X/Y format)

##### Image Navigation

- [ ] Use frame navigation buttons to move through time points
- [ ] Verify image updates correctly for each frame
- [ ] Test data type switching between different channels
- [ ] Confirm image title shows current data type and frame number
- [ ] Verify image rendering quality and contrast

#### Trace Analysis

##### Trace Loading and Display

- [ ] After visualization loads, verify traces automatically appear in trace panel
- [ ] Check trace plot shows feature dropdown with available features
- [ ] Verify trace list shows paginated traces (10 per page)
- [ ] Test feature selection changes the plot display
- [ ] Confirm trace colors follow quality scheme (blue=good, green=bad, red=active)

##### Trace Interaction

- [ ] Click on trace overlays in image viewer to select traces
- [ ] Verify selected trace appears highlighted in trace list (red color)
- [ ] Right-click on trace overlays to toggle quality (good/bad)
- [ ] Check trace plot updates when quality changes
- [ ] Test pagination controls (Previous/Next buttons)
- [ ] Verify page label shows correct current page

##### Trace Quality Management

- [ ] Select multiple traces and toggle their quality status
- [ ] Verify bad traces appear green and cannot be active
- [ ] Test trace selection with quality filtering
- [ ] Confirm trace overlays update colors based on quality
- [ ] Check trace plot reflects quality changes immediately

#### Data Export

##### Save Inspected Results

- [ ] After inspecting and modifying trace quality, click "Save Inspected CSV"
- [ ] Verify saved file is created with "_inspected" suffix
- [ ] Check status shows "filename.csv saved to [directory]"
- [ ] Confirm saved CSV contains updated quality information
- [ ] Verify file structure matches expected format with quality column

##### Error Handling

- [ ] Test loading non-existent directories
- [ ] Verify error messages for invalid project structures
- [ ] Check graceful handling of corrupted image files
- [ ] Test visualization with missing trace data
- [ ] Confirm error messages are informative and user-friendly

### Analysis Tab Tests

#### Data Loading

##### Initial Setup

- [ ] Navigate to Analysis tab
- [ ] Click "Load CSV" button and select inspected traces CSV
- [ ] Verify status bar shows "Successfully loaded [filename]"
- [ ] Check data visualization shows all traces with mean line overlay
- [ ] Confirm plot title shows "All Sequences (X cells)" where X is number of cells

##### Model Configuration

- [ ] In "Fitting" section, verify model dropdown shows available models (trivial, maturation)
- [ ] Select "Trivial" model from dropdown
- [ ] Check parameter table updates with trivial model parameters
- [ ] Verify default parameter values are populated correctly
- [ ] Test manual parameter mode by enabling manual editing
- [ ] Modify parameter values and bounds in the table
- [ ] Switch to "Maturation" model and verify parameters update

#### Fitting Execution

##### Default Fitting Test

- [ ] Click "Start Fitting" button
- [ ] Verify progress bar appears and shows "Fitting analysis models..."
- [ ] Confirm fitting completes with "Fitting completed successfully" message
- [ ] Check status shows "filename_fitted_model.csv saved to [directory]"
- [ ] Verify fitted results are automatically loaded into quality and parameter panels

##### Manual Parameter Fitting

- [ ] Enable manual parameter mode in parameter table
- [ ] Modify parameter values and bounds
- [ ] Click "Start Fitting" button with manual parameters
- [ ] Verify fitting uses custom parameter values
- [ ] Check results reflect manual parameter configuration

#### Quality Analysis

##### Fitting Quality Visualization

- [ ] After fitting completes, verify quality plot appears in "Fitting Quality" section
- [ ] Check quality plot shows R² values vs cell index with color coding
- [ ] Verify legend shows percentage breakdown (Good/Fair/Poor fits)
- [ ] Confirm color scheme: green (R²>0.9), yellow (0.7<R²≤0.9), red (R²≤0.7)
- [ ] Test quality plot updates when new fitting results are loaded

##### Individual Trace Inspection

- [ ] Click "Show Random Trace" button in "Fitted Traces" section
- [ ] Verify random trace displays with raw data (blue) and fitted curve (red)
- [ ] Check trace title shows cell ID, model type, R² value, and fit status
- [ ] Test multiple random traces to see different fitting qualities
- [ ] Verify trace plot updates correctly for each random selection

#### Parameter Analysis

##### Parameter Distribution Visualization

- [ ] After fitting completes, verify parameter dropdown is populated
- [ ] Select different parameters from "Single Parameter" dropdown
- [ ] Check histogram updates to show parameter distribution
- [ ] Verify histogram title shows "Distribution of [parameter_name]"
- [ ] Test "Good fits only (R² > 0.9)" checkbox filtering
- [ ] Confirm histogram updates when filter is toggled

##### Parameter Correlation Analysis

- [ ] Select X and Y parameters from "Double Parameter" dropdowns
- [ ] Verify scatter plot updates to show parameter correlation
- [ ] Check scatter plot title shows "Scatter Plot: X vs Y"
- [ ] Test filtering with "Good fits only" checkbox
- [ ] Confirm scatter plot updates when filter is applied
- [ ] Navigate through different parameter combinations

#### Results Export

##### Save Analysis Plots

- [ ] Click "Save All Plots" button
- [ ] Choose output directory for plots
- [ ] Verify status shows "Saved histogram to [path]" messages
- [ ] Check that individual parameter histograms are saved as PNG files
- [ ] Confirm scatter plots are saved with naming pattern "scatter_X_vs_Y.png"
- [ ] Verify all plots are saved at 300 DPI resolution

##### Load Existing Results

- [ ] Click "Load Fitted Results" button
- [ ] Select previously saved fitted results CSV
- [ ] Verify results load into quality and parameter panels
- [ ] Check that quality plot and parameter analysis update correctly
- [ ] Confirm trace visualization works with loaded results

### Cross-Tab Integration Tests

#### Data Flow Validation

##### Processing to Visualization Pipeline

- [ ] Process data in Processing tab with complete workflow
- [ ] Navigate to Visualization tab and verify "Load Folder" shows processed results
- [ ] Load processed results directory in Visualization tab
- [ ] Verify FOV count and available channels match processing output
- [ ] Check that trace data is accessible from processed results

##### Visualization to Analysis Pipeline

- [ ] After inspecting traces in Visualization tab, save inspected CSV
- [ ] Navigate to Analysis tab and load the inspected traces CSV
- [ ] Verify trace data loads correctly with proper formatting
- [ ] Check that cell IDs and time series data are preserved
- [ ] Confirm analysis can proceed with inspected data

##### Analysis Results Export

- [ ] Complete fitting analysis in Analysis tab
- [ ] Verify fitted results CSV is created with proper naming
- [ ] Check that parameter analysis plots can be exported
- [ ] Confirm exported files contain expected data and metadata
- [ ] Test loading exported results in subsequent sessions

#### Cross-Tab State Management

##### Tab Switching and Data Persistence

- [ ] Load data in Processing tab, switch to Visualization, then back to Processing
- [ ] Verify loaded microscopy file and parameters are preserved
- [ ] Load visualization data, switch to Analysis, then back to Visualization
- [ ] Check that loaded project data and visualization state are maintained
- [ ] Test switching between all tabs with different data loaded

##### Status Message Coordination

- [ ] Start processing workflow and switch to other tabs
- [ ] Verify status messages update correctly across tabs
- [ ] Check that progress indicators work when switching tabs
- [ ] Confirm error messages appear in appropriate tabs
- [ ] Test status message consistency during cross-tab operations

#### Error Handling

##### File Format Validation

- [ ] Try loading non-ND2 files in Processing tab
- [ ] Attempt to load non-CSV files in Analysis tab
- [ ] Test loading invalid directory structures in Visualization tab
- [ ] Verify error messages are informative and actionable
- [ ] Check that UI state is properly reset after errors

##### Data Integrity Checks

- [ ] Test processing with corrupted ND2 files
- [ ] Attempt analysis with malformed CSV files
- [ ] Try visualization with incomplete processing results
- [ ] Verify graceful degradation when data is missing
- [ ] Confirm error recovery mechanisms work correctly

### Performance Tests

#### Large Dataset Processing

##### Multi-FOV Workflow Performance

- [ ] Test processing with dataset containing 5+ FOVs
- [ ] Verify UI remains responsive during long processing operations
- [ ] Check memory usage stays within reasonable bounds
- [ ] Monitor processing time for different FOV counts
- [ ] Test cancellation and cleanup with large datasets

##### Visualization Performance

- [ ] Load visualization with large number of time points (100+ frames)
- [ ] Test frame navigation performance with large datasets
- [ ] Verify trace rendering performance with many cells (1000+)
- [ ] Check memory usage during trace pagination
- [ ] Test image rendering quality with high-resolution data

##### Analysis Performance

- [ ] Test fitting performance with large trace datasets (1000+ cells)
- [ ] Verify parameter analysis rendering with many parameters
- [ ] Check plot export performance for large result sets
- [ ] Monitor memory usage during fitting operations
- [ ] Test analysis with multiple model types sequentially

#### User Interface Responsiveness

##### Background Operation Handling

- [ ] Verify UI remains responsive during background processing
- [ ] Test tab switching during long-running operations
- [ ] Check progress indicators update smoothly
- [ ] Verify cancellation works promptly for all operations
- [ ] Test UI responsiveness with multiple operations queued

##### Memory Management

- [ ] Monitor memory usage during extended testing sessions
- [ ] Test memory cleanup when switching between datasets
- [ ] Verify no memory leaks during repeated operations
- [ ] Check memory usage with different data sizes
- [ ] Test application stability over extended periods

### User Experience Tests

#### Interface Consistency

##### UI Element Validation

- [ ] Verify all buttons have descriptive tooltips when hovered
- [ ] Check that all dropdown menus show appropriate options
- [ ] Test that progress bars appear for long-running operations
- [ ] Verify status messages are clear and informative
- [ ] Check that error messages provide actionable guidance

##### Layout and Responsiveness

- [ ] Test window resizing and verify layout adapts correctly
- [ ] Check that dialogs are properly sized and centered
- [ ] Verify panel proportions remain consistent when resizing
- [ ] Test UI behavior at different screen resolutions
- [ ] Confirm scroll bars appear when content exceeds panel size

##### Keyboard and Accessibility

- [ ] Test keyboard navigation between UI elements
- [ ] Verify Tab key navigation works logically
- [ ] Check that Enter key activates appropriate buttons
- [ ] Test Escape key behavior in dialogs and panels
- [ ] Verify keyboard shortcuts work as expected

#### Workflow Intuitiveness

##### Complete Workflow Testing

- [ ] Test complete workflow from ND2 file to analysis results without documentation
- [ ] Verify navigation flow is logical (Processing → Visualization → Analysis)
- [ ] Check that each step clearly indicates what to do next
- [ ] Confirm progress indicators provide meaningful feedback
- [ ] Test that users can understand the purpose of each tab

##### Error Prevention and Recovery

- [ ] Verify required fields are clearly marked or validated
- [ ] Test that invalid inputs are caught before processing
- [ ] Check that users can recover from common mistakes
- [ ] Confirm error messages help users understand what went wrong
- [ ] Test that users can restart operations after errors

##### Data Management Clarity

- [ ] Verify file loading dialogs show appropriate file filters
- [ ] Check that output file naming is clear and consistent
- [ ] Test that users can easily locate saved results
- [ ] Confirm data flow between tabs is transparent
- [ ] Verify that data persistence across sessions works as expected

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

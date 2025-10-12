# PyAMA-Qt Refactoring Validation Plan

This document outlines a detailed validation plan to compare the original PyAMA-Qt (pyama-v011) with the refactored version (pyama-vibe) at the method level.

## Objectives
- Ensure all functionality from the original version is preserved in the refactored version
- Validate that no features are lost during the MVC to consolidated architecture refactoring
- Verify that all public APIs remain consistent
- Confirm that all UI workflows function identically

## Method-Level Comparison Plan

### 1. Processing Module Comparison

#### Original Files (pyama-v011):
- `src/pyama_qt/views/processing/page.py`
- `src/pyama_qt/views/processing/workflow_panel.py` 
- `src/pyama_qt/views/processing/merge_panel.py`
- `src/pyama_qt/controllers/processing.py`
- `src/pyama_qt/models/processing.py`

#### Refactored File (pyama-vibe):
- `src/pyama_qt/processing/main_tab.py`
- `src/pyama_qt/processing/workflow.py`
- `src/pyama_qt/processing/merge.py`

#### Validation Steps:
1. Compare all public methods in workflow panel between original and refactored
   - `set_channel_options()` → `_build_channel_section()` integration
   - `display_microscopy_path()` → Direct state updates
   - `set_parameter_defaults()` → Parameter panel integration
   - All signal definitions and their connections

2. Compare all public methods in merge panel between original and refactored
   - `load_samples()` → Direct table population
   - `current_samples()` → Table data extraction
   - All signal definitions and their connections

3. Validate all controller logic moved to main_tab.py
   - `_on_microscopy_selected()` equivalent functionality
   - `_on_process_requested()` equivalent workflow execution
   - `_on_merge_requested()` equivalent merge execution

### 2. Analysis Module Comparison

#### Original Files (pyama-v011):
- `src/pyama_qt/views/analysis/page.py`
- `src/pyama_qt/views/analysis/data_panel.py`
- `src/pyama_qt/views/analysis/fitting_panel.py`
- `src/pyama_qt/views/analysis/results_panel.py`
- `src/pyama_qt/controllers/analysis.py`
- `src/pyama_qt/models/analysis.py`

#### Refactored Files (pyama-vibe):
- `src/pyama_qt/analysis/main_tab.py`
- `src/pyama_qt/analysis/data.py`
- `src/pyama_qt/analysis/fitting.py`
- `src/pyama_qt/analysis/results.py`

#### Validation Steps:
1. Compare all public methods in data panel between original and refactored
   - `clear_plot()` → Direct canvas clearing
   - `render_plot()` → Internal plot rendering
   - `csv_selected` signal and connections

2. Compare all public methods in fitting panel between original and refactored
   - `set_available_models()` → Model combo population
   - `set_parameter_defaults()` → Parameter panel setup
   - `show_cell_visualization()` → QC plot rendering
   - All signal definitions and their connections

3. Validate controller logic migration to individual components
   - Fitting workflow execution
   - Data loading and processing
   - Result handling and display

### 3. Visualization Module Comparison

#### Original Files (pyama-v011):
- `src/pyama_qt/views/visualization/page.py`
- `src/pyama_qt/views/visualization/project_panel.py`
- `src/pyama_qt/views/visualization/image_panel.py`
- `src/pyama_qt/views/visualization/trace_panel.py`
- `src/pyama_qt/controllers/visualization.py`
- `src/pyama_qt/models/visualization.py`

#### Refactored Files (pyama-vibe):
- `src/pyama_qt/visualization/main_tab.py`
- `src/pyama_qt/visualization/project.py`
- `src/pyama_qt/visualization/image.py`
- `src/pyama_qt/visualization/trace.py`
- `src/pyama_qt/visualization/models.py`

#### Validation Steps:
1. Compare all public methods in project panel between original and refactored
   - `set_project_details()` → UI updates
   - `set_available_channels()` → Channel list population
   - All signal definitions and connections

2. Compare all public methods in image panel between original and refactored
   - `render_image()` → Canvas rendering
   - `set_frame_info()` → Frame navigation
   - `_draw_trace_overlays()` → Overlay drawing

3. Compare all public methods in trace panel between original and refactored
   - `set_trace_dataset()` → Data loading
   - `set_active_trace()` → Trace selection
   - `_plot_current_page_selected()` → Plot rendering

### 4. Signal and Event Handler Comparison

#### Validation Steps:
1. Catalog all signals in original version and verify equivalent functionality in refactored version
2. Verify event handlers are properly connected and function identically
3. Test that UI state changes propagate correctly between components

### 5. Threading and Background Processing Comparison

#### Validation Steps:
1. Compare worker implementations and threading patterns
2. Verify all background processing functionality is preserved
3. Ensure cancellation and progress reporting works identically

### 6. Integration Testing

#### Validation Steps:
1. Test complete processing workflow from ND2 file to results
2. Test complete analysis workflow from CSV loading to fitting
3. Test complete visualization workflow from project loading to trace inspection
4. Verify cross-tab interactions (e.g., processing results affecting visualization)

### 7. UI Workflow Validation

#### Validation Steps:
1. Create manual test scenarios for each feature
2. Verify that all UI elements behave identically
3. Test data flow between different components
4. Verify error handling and user feedback

### 8. Code Coverage Validation

#### Validation Steps:
1. Ensure all original methods have equivalent functionality in refactored version
2. Verify no functionality was accidentally removed during refactoring
3. Confirm that all edge cases are handled identically

### Validation Checklist Template

For each comparison, use this template:

```
Original File: [file_path]
Refactored File: [file_path]

Method: [method_name]
- Original signature: [signature]
- Refactored equivalent: [method_or_functionality]
- Behavior preserved: [yes/no]
- Input validation: [same/different]
- Output behavior: [same/different]
- Side effects: [same/different]
- Test status: [pass/fail/pending]
```
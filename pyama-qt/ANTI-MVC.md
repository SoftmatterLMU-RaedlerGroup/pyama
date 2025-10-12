# ANTI-MVC Plan: Consolidating PyAMA-Qt Architecture

## Problem Statement
The current PyAMA-Qt application follows an overly complex MVC (Model-View-Controller) architecture that has become difficult to maintain. The separation of concerns has led to:
- Excessive indirection and complexity
- Difficulty in understanding data flow
- Hard-to-debug interactions between components
- Unnecessarily fragmented codebase

## Solution Approach
Eliminate the MVC architecture and consolidate into a more straightforward structure with:
- Direct View-Model integration without controllers
- Merged functionality by feature rather than by architectural layer
- Simplified data flow and state management
- Reduced cognitive overhead for developers

## Structure After Consolidation

### Main Components
- **main_window.py**: Top-level window that orchestrates all three tabs
- **processing/**: Contains all processing-related functionality
  - `workflow.py`: Handles processing workflow configuration and execution
  - `merge.py`: Handles sample merging and configuration
  - `main_tab.py`: Combines processing UI components
- **analysis/**: Contains all analysis-related functionality
  - `data.py`: Manages analysis data loading and processing
  - `fitting.py`: Handles trace fitting operations and model selection
  - `results.py`: Manages fitting results and visualization
  - `main_tab.py`: Combines analysis UI components
- **visualization/**: Contains all visualization-related functionality
  - `project.py`: Manages project loading and channel selection
  - `image.py`: Handles image display and navigation
  - `trace.py`: Manages trace visualization and selection
  - `main_tab.py`: Combines visualization UI components

## Migration Strategy

### Phase 1: Consolidate Views
1. Merge View and Controller logic where appropriate
2. Simplify Model access patterns
3. Maintain UI components in separate modules for clarity

### Phase 2: Consolidate Models
1. Simplify model-to-view communication
2. Remove unnecessary abstraction layers
3. Use direct method calls instead of complex signal chains

### Phase 3: Update Main Application
1. Update main.py to use new consolidated structure
2. Update imports to point to new module locations
3. Remove old MVC components after verification

## Benefits of the New Structure
- Reduced complexity and indirection
- Easier debugging and maintenance
- Faster development iterations
- Clearer feature boundaries
- Simplified testing
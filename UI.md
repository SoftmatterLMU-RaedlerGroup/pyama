# PyAMA-Qt User Interface Documentation

## Overview

PyAMA-Qt provides a clean, modern PySide6-based graphical user interface for microscopy image processing workflows. The application features a horizontal split-pane layout with file loading on the left and processing workflow on the right.

## Architecture

### Project Structure
```
src/pyama_qt/ui/
├── __init__.py
├── main_window.py          # Main application window
└── widgets/
    ├── __init__.py
    ├── fileloader.py       # File loading and channel assignment
    └── workflow.py         # Processing workflow interface
```

### Class Hierarchy
- **MainWindow**: Main application container
- **FileLoader**: ND2 file loading and channel assignment
- **Workflow**: Sequential processing workflow management

## Main Window (MainWindow)

### Window Properties
- **Title**: "PyAMA Processing Tool"
- **Default Size**: 800x500 pixels
- **Layout**: Horizontal QSplitter (350:650 ratio)
- **Resizable**: Yes, with user-adjustable splitter

### Menu Structure
```
File
├── Load ND2 File    # Opens file dialog
└── Exit            # Closes application

Help
└── About           # Application information
```

### Status Bar
- **Initial State**: "Ready"
- **File Loaded**: "Loaded: /full/path/to/file.nd2"
- **Status Updates**: Real-time feedback from file loading operations

## File Loader Widget (FileLoader)

### Layout
- **Position**: Left pane of main window
- **Compact Design**: Minimal vertical space usage with stretch to push content to top

### File Selection Section
```
┌─ File Selection ──────────────┐
│ [filename.nd2 or "No ND2..."] │
│ [Select ND2 File]             │
└───────────────────────────────┘
```

**Features:**
- **File Label**: Shows filename only when loaded, bordered display
- **Select Button**: Opens ND2 file dialog
- **Loading State**: Shows "Loading: filename.nd2" during file processing

### Channel Assignment Section
```
┌─ Channel Assignment ──────────┐
│ Phase Contrast: [Dropdown▼]  │
│ Fluorescence:   [Dropdown▼]  │
│ [Load Data]                   │
└───────────────────────────────┘
```

**Features:**
- **Horizontal Layout**: Label:Dropdown pairs for compact display
- **Channel Options**: "None" + "Channel X: channel_name" format
- **Data Storage**: Dropdown stores channel name strings, converts to indices
- **Load Button**: Enabled only after file loading, validates channel selection

### Data Flow
1. **File Selection**: User selects ND2 file via dialog
2. **Background Loading**: ND2LoaderThread extracts comprehensive metadata
3. **Channel Population**: Dropdowns populated with available channels
4. **Channel Assignment**: User assigns phase contrast and/or fluorescence channels
5. **Data Loading**: Creates data_info structure with both indices and names
6. **Signal Emission**: Emits data_loaded and status_message signals

### ND2 Metadata Structure
```python
ND2Metadata = {
    # File info
    'filepath': str,
    'filename': str,
    
    # Complete metadata from images.metadata
    'channels': List[str],
    'date': datetime,
    'experiment': Dict,
    'height': int, 'width': int,
    'pixel_microns': float,
    # ... all other ND2 metadata fields
    
    # Complete sizes from images.sizes  
    'sizes': {'c': int, 't': int, 'v': int, 'x': int, 'y': int, 'z': int},
    
    # Derived convenience properties
    'n_channels': int,
    'n_frames': int,
    'n_fov': int,
    'n_z_levels': int
}
```

## Workflow Widget (Workflow)

### Layout
- **Position**: Right pane of main window
- **Sections**: Sequential workflow steps, output settings, processing controls

### Processing Workflow Section
```
┌─ Processing Workflow ─────────────────────┐
│ ● Step 1: Segmentation (Binarization)    │
│ ─────────────────────────────────────────  │
│ ● Step 2: Background Correction          │
│ ─────────────────────────────────────────  │
│ ● Step 3: Cell Tracking                  │
│ ─────────────────────────────────────────  │
│ ● Step 4: Pickle Maximum Bounding Box    │
└───────────────────────────────────────────┘
```

**Features:**
- **Signal Lights**: Circular indicators (●) on the left of each step
- **Status Colors**:
  - Gray (#cccccc): Pending/not started
  - Orange (#FFA500): Processing
  - Green (#4CAF50): Completed successfully  
  - Red (#F44336): Failed
- **Normal Text**: Clean, readable step labels without bold/color styling
- **Visual Separators**: Horizontal lines between steps

### Output Settings Section
```
┌─ Output Settings ─────────────────────────┐
│ Output Directory: [path/to/dir] [Browse]  │
│ Output files will use ND2 filename as    │
│ base (e.g., filename_segmented.npz)      │
└───────────────────────────────────────────┘
```

**Features:**
- **Directory Selection**: Browse dialog for output location
- **Automatic Naming**: Uses ND2 filename as base for all outputs
- **File Extensions**: Different extensions for each processing step

### Processing Control Section
```
┌─ Processing Control ──────────────────────┐
│ [Start Complete Workflow]                 │
│ ████████████████████████████████ 45%     │
│ ┌─ Log Area ─────────────────────────────┐│
│ │ Starting complete workflow...          ││
│ │ Processing: Segmentation → Background  ││
│ │ Correction → Tracking → Bounding Box  ││
│ │ ✓ Segmentation completed successfully  ││
│ └────────────────────────────────────────┘│
└───────────────────────────────────────────┘
```

**Features:**
- **Process Button**: Large, styled button to start workflow
- **Progress Bar**: Overall workflow progress indicator (always visible)
- **Log Area**: Real-time status messages and completion notifications
- **Status Updates**: Shows current step and completion status

### Default Processing Parameters
```python
DEFAULT_PARAMS = {
    'mask_size': 3,           # Segmentation
    'div_horiz': 7,           # Background correction horizontal divisions
    'div_vert': 5,            # Background correction vertical divisions
    'use_memmap': True,       # Memory mapping for large files
    'max_displacement': 20,   # Cell tracking max displacement (pixels)
    'memory_frames': 3,       # Cell tracking memory frames
}
```

### Workflow Data Structure
```python
workflow_params = {
    'data_info': dict,                    # Complete ND2 metadata and channel info
    'output_dir': str,                    # Selected output directory
    'base_name': str,                     # ND2 filename without extension
    'enabled_steps': List[str],           # All steps enabled by default
    **DEFAULT_PARAMS                      # Default processing parameters
}
```

## Signal Architecture

### Inter-Widget Communication
```
FileLoader → MainWindow → Workflow
    │            │           │
    └─data_loaded─┴→update───┘
    └─status_message→status_bar
```

### Key Signals
- **FileLoader.data_loaded(dict)**: Emits complete data info when ready
- **FileLoader.status_message(str)**: Status updates for main window
- **Workflow.process_requested(dict)**: Workflow execution parameters

## State Management

### Application States
1. **Initial**: No file loaded, workflow disabled
2. **Loading**: File being processed, UI feedback active  
3. **Ready**: File loaded, channels assigned, workflow enabled
4. **Processing**: Workflow executing, progress tracking active
5. **Complete**: Processing finished, results available
6. **Error**: Error state with appropriate user feedback

### UI State Synchronization
- **File Loading**: Enables/disables UI elements based on loading state
- **Channel Assignment**: Validates selections before enabling workflow
- **Processing State**: Locks UI during processing, shows progress
- **Signal Light Updates**: Real-time visual feedback for workflow steps

## Design Principles

### Visual Design
- **Clean Minimalism**: Focused on essential functionality
- **Horizontal Layout**: Efficient use of screen space
- **Compact Sections**: Minimal vertical space usage
- **Professional Styling**: Consistent with modern desktop applications

### User Experience
- **Logical Flow**: Left-to-right progression (load → process)
- **Visual Feedback**: Clear status indication at all stages
- **Error Handling**: Graceful error messages and recovery
- **Responsive Design**: Resizable interface adapts to user preferences

### Technical Architecture
- **Separation of Concerns**: UI, data, and processing logic separated
- **Signal-Slot Pattern**: Clean inter-component communication
- **Background Threading**: Non-blocking file operations
- **Type Safety**: Comprehensive type annotations for data structures

## Usage Workflow

1. **Launch**: `python -m pyama_qt`
2. **Load File**: Select ND2 file via "Select ND2 File" button
3. **Assign Channels**: Choose phase contrast and/or fluorescence channels
4. **Load Data**: Click "Load Data" to prepare for processing
5. **Set Output**: Choose output directory for results
6. **Process**: Click "Start Complete Workflow" to begin processing
7. **Monitor**: Watch signal lights and progress bar for status
8. **Complete**: Review log messages and locate output files

The UI provides a streamlined, professional interface for complex microscopy image processing workflows while maintaining simplicity and ease of use.
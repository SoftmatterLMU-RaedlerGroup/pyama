# Design Document

## Overview

The PyAMA-Qt merge app is designed as a standalone Qt application that bridges the processing and analysis modules. It follows the established PyAMA-Qt architecture pattern with a main window, service layer, and core data types. The app transforms individual FOV trace CSV files into sample-level CSV files suitable for analysis.

The application consists of three main components:
1. **Data Discovery and Loading**: Automatically discovers and loads FOV trace CSV files from processing output directories
2. **Sample Grouping Interface**: Table-based UI for defining sample groups using FOV range notation
3. **Data Merging and Export**: Converts processing format to analysis format and exports sample CSV files

## Architecture

### Application Structure
```
pyama-qt/src/pyama_qt/merge/
├── __init__.py
├── main.py                    # Application entry point
├── services/
│   ├── __init__.py
│   ├── discovery.py           # FOV file discovery service
│   ├── merge.py              # Data merging service
│   └── validation.py         # Data validation utilities
├── ui/
│   ├── __init__.py
│   ├── main_window.py        # Main application window
│   └── widgets/
│       ├── __init__.py
│       ├── fov_table.py      # FOV information display
│       ├── sample_table.py   # Sample grouping table
│       └── statistics.py    # Sample statistics widget
└── utils/
    ├── __init__.py
    ├── fov_parser.py         # FOV range parsing utilities
    └── csv_converter.py      # Format conversion utilities
```

### Core Data Types (pyama-core)
```
pyama-core/src/pyama_core/io/
├── processing_csv.py         # Processing CSV format definitions (used by processing & visualization modules)
└── analysis_csv.py          # Analysis CSV format definitions (used by analysis module)
```

**Critical Design Decision**: All CSV format definitions and related utilities will be centralized in pyama-core to ensure consistency across modules:
- Processing module will use `processing_csv.py` for trace output
- Visualization module will use `processing_csv.py` for trace loading and filtering
- Analysis module will use `analysis_csv.py` for data input
- Merge module will import both formats for conversion between them

## Components and Interfaces

### 1. Data Discovery Service (`services/discovery.py`)

**Purpose**: Discovers and loads FOV trace CSV files from processing output directories.

**Key Classes**:
- `FOVDiscoveryService`: Main service class for file discovery
- `FOVInfo`: Data class containing FOV metadata (index, cell count, file path)

**Key Methods**:
```python
class FOVDiscoveryService:
    def discover_fov_files(self, output_dir: Path) -> List[FOVInfo]
    def load_fov_metadata(self, csv_path: Path) -> FOVInfo
    def prioritize_inspected_files(self, files: List[Path]) -> List[Path]
```

**Interface**: 
- Input: Processing output directory path
- Output: List of FOVInfo objects with metadata
- Prioritizes files with 'inspected' suffix over regular trace files
- Uses `pyama_core.io.processing_csv` for format validation and parsing

### 2. Data Merging Service (`services/merge.py`)

**Purpose**: Converts processing CSV format to analysis CSV format and handles sample grouping.

**Key Classes**:
- `MergeService`: Main service for data transformation
- `SampleGroup`: Data class representing a sample with assigned FOVs

**Key Methods**:
```python
class MergeService:
    def create_sample_group(self, name: str, fov_ranges: str) -> SampleGroup
    def validate_fov_ranges(self, ranges: str, available_fovs: List[int]) -> bool
    def merge_sample_data(self, sample: SampleGroup, fov_data: Dict[int, pd.DataFrame]) -> pd.DataFrame
    def export_sample_csv(self, sample_data: pd.DataFrame, output_path: Path) -> None
```

**Interface**:
- Input: Sample definitions and FOV data (using `pyama_core.io.processing_csv` format)
- Output: Analysis-format CSV files (using `pyama_core.io.analysis_csv` format)
- Handles format conversion between processing and analysis formats
- Manages cell ID renumbering and time unit conversion

### 3. Main Window (`ui/main_window.py`)

**Purpose**: Primary application interface coordinating all components.

**Key Features**:
- File browser for selecting processing output directory
- FOV information display
- Sample grouping table
- Statistics display
- Export functionality

**Layout**:
```
┌─────────────────────────────────────────┐
│ File: [Browse...] [Selected Directory]  │
├─────────────────────────────────────────┤
│ FOV Information                         │
│ ┌─────────────────────────────────────┐ │
│ │ FOV Index │ Cell Count              │ │
│ │    0      │    45                   │ │
│ │    1      │    52                   │ │
│ │   ...     │   ...                   │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ Sample Grouping                         │
│ ┌─────────────────────────────────────┐ │
│ │ Name      │ FOVs                    │ │
│ │ Sample_1  │ 0-4,6                   │ │
│ │ Sample_2  │ 5,7-10                  │ │
│ │   ...     │   ...                   │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ Sample Statistics                       │
│ ┌─────────────────────────────────────┐ │
│ │ Selected: Sample_1                  │ │
│ │ FOVs: 0,1,2,3,4,6 (6 FOVs)          │ │
│ │ Total Cells: 287                    │ │
│ │ Time Points: 120                    │ │
│ └─────────────────────────────────────┘ │
├─────────────────────────────────────────┤
│ [Export Samples] [Save Config] [Load]   │
└─────────────────────────────────────────┘
```

### 4. FOV Table Widget (`ui/widgets/fov_table.py`)

**Purpose**: Displays discovered FOV information in a read-only table.

**Features**:
- Two-column table: FOV Index, Cell Count
- Automatic population from discovery service
- Read-only display

### 5. Sample Table Widget (`ui/widgets/sample_table.py`)

**Purpose**: Editable table for defining sample groups with FOV range notation.

**Features**:
- Two-column editable table: Name, FOVs
- Real-time validation of FOV ranges
- Add/remove sample rows
- Selection handling for statistics display

**FOV Range Parsing**:
- Supports comma-separated values: "1,3,5"
- Supports ranges: "1-5" (expands to 1,2,3,4,5)
- Supports mixed notation: "1-4,6,9-20"
- Uses 0-based indexing
- Validates against available FOVs

### 6. Statistics Widget (`ui/widgets/statistics.py`)

**Purpose**: Displays detailed information about selected sample groups.

**Features**:
- Shows resolved FOV indices
- Displays FOV count and total cell count
- Shows time points and available features
- Updates when sample selection changes
- Error display for invalid ranges

## Data Models

### Processing CSV Format (Input) - Defined in `pyama_core.io.processing_csv`
```python
# File: {base_name}_fov{index:04d}_traces.csv
# Columns: fov, cell_id, frame, intensity_total, area, x_centroid, y_centroid, [good]
@dataclass
class ProcessingTraceRecord:
    fov: int
    cell_id: int
    frame: int
    intensity_total: float
    area: float
    x_centroid: float
    y_centroid: float
    good: bool = True  # Optional, from visualization filtering

class ProcessingCSVLoader:
    def load_fov_traces(self, csv_path: Path) -> pd.DataFrame
    def validate_format(self, df: pd.DataFrame) -> bool
    def get_cell_count(self, csv_path: Path) -> int
```

### Analysis CSV Format (Output) - Defined in `pyama_core.io.analysis_csv`
```python
# File: {sample_name}.csv
# Format: time as index, cells as columns (0,1,2,3...)
# First row: header with cell IDs
# Subsequent rows: time values and intensity data
class AnalysisCSVWriter:
    def write_sample_data(self, df: pd.DataFrame, output_path: Path) -> None
    def validate_format(self, df: pd.DataFrame) -> bool
    
# Expected DataFrame structure:
# Index: time (hours), Columns: cell IDs (0,1,2,3...)
AnalysisDataFrame = pd.DataFrame  # Index: float (time), Columns: int (cell_ids)
```

### Internal Data Models
```python
@dataclass
class FOVInfo:
    index: int
    cell_count: int
    file_path: Path
    has_quality_data: bool

@dataclass 
class SampleGroup:
    name: str
    fov_ranges: str
    resolved_fovs: List[int]
    total_cells: int
    
@dataclass
class MergeConfiguration:
    samples: List[SampleGroup]
    output_directory: Path
    min_trace_length: int = 0
```

## Error Handling

### Validation Strategy
1. **File Discovery**: Log warnings for unreadable files, continue with available data
2. **FOV Range Parsing**: Validate syntax and FOV existence, show errors in statistics widget
3. **Data Merging**: Check format compatibility, log inconsistencies
4. **Export**: Validate output directory permissions, handle file write errors

### Logging Approach
- Use Python logging module with console output
- Log levels: INFO for normal operations, WARNING for recoverable issues, ERROR for failures
- Detailed error messages with context and suggested solutions

## Testing Strategy

### Unit Tests
- FOV range parsing utilities
- CSV format conversion functions
- Data validation logic
- Sample group creation and validation

### Integration Tests
- End-to-end file discovery and loading
- Complete merge workflow with sample data
- Export functionality with various sample configurations
- Error handling scenarios

### UI Tests
- Table widget interactions
- File browser functionality
- Statistics display updates
- Export button behavior

### Test Data
- Create sample processing output directories with various FOV configurations
- Include both regular and 'inspected' CSV files
- Test edge cases: empty FOVs, missing files, invalid formats

## Performance Considerations

### Memory Management
- Load FOV metadata only (not full trace data) during discovery
- Stream CSV data during merging to handle large datasets
- Clear intermediate data structures after processing

### Scalability
- Support for hundreds of FOVs per experiment
- Efficient FOV range parsing and validation
- Progress indicators for long-running operations

### User Experience
- Real-time validation feedback
- Non-blocking UI during file operations
- Clear progress indication during export
# Requirements Document

## Introduction

The PyAMA-Qt merge app is a critical component that bridges the processing and analysis modules in the PyAMA microscopy analysis pipeline. Timelapse microscopy experiments typically involve multiple fields of view (FOVs) across different samples, and the processing module handles each FOV individually. The merge app allows users to group FOVs by sample and convert the processing output format to the analysis input format, enabling seamless workflow from image processing to statistical analysis.

The app transforms individual FOV trace CSV files (format: `fov, cell_id, frame, [features...]`) into sample-level CSV files (format: `time, cell1, cell2, cell3...`) that can be consumed by the analysis module.

## Requirements

### Requirement 1

**User Story:** As a microscopy researcher, I want to load and view processing results from multiple FOVs, so that I can see all available trace data before grouping them into samples.

#### Acceptance Criteria

1. WHEN the user opens the merge app THEN the system SHALL display a file browser to select a processing output directory
2. WHEN a valid processing directory is selected THEN the system SHALL automatically discover all FOV trace CSV files, prioritizing files with 'inspected' suffix over regular trace files
3. WHEN FOV files are discovered THEN the system SHALL display a table with FOV index and number of cells for each available FOV
4. IF no valid trace files are found THEN the system SHALL display an informative error message
5. WHEN FOV data is loaded THEN the system SHALL validate the CSV format matches the expected processing output format

### Requirement 2

**User Story:** As a microscopy researcher, I want to create and manage sample groups by assigning FOVs to samples using a table interface, so that I can efficiently organize my experimental data according to my study design.

#### Acceptance Criteria

1. WHEN FOV data is loaded THEN the system SHALL provide a table widget with columns "Name" and "FOVs" for sample grouping
2. WHEN the user enters a sample name THEN the system SHALL allow them to type it directly in the "Name" column
3. WHEN the user specifies FOVs THEN the system SHALL accept range notation in the "FOVs" column (e.g., "1-4,6,9-20" for FOVs 1,2,3,4,6,9,10,11...20)
4. WHEN FOV ranges are entered THEN the system SHALL use 0-based indexing for all FOV references
5. WHEN the user enters FOV ranges THEN the system SHALL validate that all specified FOVs exist in the loaded dataset
6. WHEN FOVs are assigned to samples THEN the system SHALL prevent the same FOV from being assigned to multiple samples
7. WHEN sample definitions are complete THEN the system SHALL display a summary showing resolved FOV count and estimated cell count per sample

### Requirement 3

**User Story:** As a microscopy researcher, I want to see detailed merge statistics for selected samples, so that I can verify the grouping is correct before export.

#### Acceptance Criteria

1. WHEN the sample grouping interface is displayed THEN the system SHALL provide a statistics widget below the sample table
2. WHEN the user clicks on a sample row THEN the system SHALL display detailed statistics for that sample in the statistics widget
3. WHEN displaying sample statistics THEN the system SHALL show resolved FOV indices, FOV count, total cell count, and time points
4. WHEN FOV ranges are invalid THEN the system SHALL display error information in the statistics widget
5. WHEN no sample is selected THEN the statistics widget SHALL display instructions to select a sample row

### Requirement 4

**User Story:** As a microscopy researcher, I want to export merged sample data to CSV files compatible with the analysis module, so that I can proceed with statistical analysis and model fitting.

#### Acceptance Criteria

1. WHEN the user initiates export THEN the system SHALL validate that all samples have at least one assigned FOV
2. WHEN exporting samples THEN the system SHALL convert from processing format (fov, cell_id, frame, features) to analysis format (time as index, cells as columns)
3. WHEN generating analysis CSV files THEN the system SHALL use time in hours as the index (converted from frame numbers)
4. WHEN creating merged files THEN the system SHALL generate sequential cell identifiers (0,1,2,3,4...) across FOVs within each sample
5. WHEN export is complete THEN the system SHALL save files with naming convention `{sample_name}.csv`
6. WHEN files are saved THEN the system SHALL display a success message with output file paths

### Requirement 5

**User Story:** As a microscopy researcher, I want to filter and quality control the trace data during merging, so that only good quality traces are included in the final analysis dataset.

#### Acceptance Criteria

1. WHEN FOV data contains 'good' column THEN the system SHALL respect the quality filtering from visualization module
2. WHEN merging traces THEN the system SHALL only include traces marked as 'good' if quality data is available
3. WHEN no quality data is available THEN the system SHALL include all traces by default
4. WHEN the user configures merge settings THEN the system SHALL allow minimum trace length filtering
5. WHEN applying filters THEN the system SHALL display how many traces were excluded and why

### Requirement 6

**User Story:** As a microscopy researcher, I want to save and load sample grouping configurations, so that I can reuse groupings for similar experiments or modify them later.

#### Acceptance Criteria

1. WHEN sample groups are defined THEN the system SHALL provide an option to save the grouping configuration
2. WHEN saving configurations THEN the system SHALL store sample names, FOV assignments, and merge settings in a JSON file
3. WHEN loading a saved configuration THEN the system SHALL restore sample groups and settings if the referenced FOV files exist
4. IF referenced FOV files are missing THEN the system SHALL display warnings and allow manual reassignment
5. WHEN configurations are loaded THEN the system SHALL validate compatibility with the current dataset

### Requirement 7

**User Story:** As a microscopy researcher, I want clear error handling and validation through console logging, so that I can understand and resolve any issues with my data or grouping configuration.

#### Acceptance Criteria

1. WHEN invalid CSV files are encountered THEN the system SHALL log specific error messages to console indicating the issue
2. WHEN FOVs have incompatible data formats THEN the system SHALL prevent grouping and log the incompatibility details
3. WHEN export fails THEN the system SHALL log detailed error information and suggested solutions to console
4. WHEN the system encounters missing files THEN the system SHALL gracefully handle the error, log warnings, and continue with available data
5. WHEN data validation fails THEN the system SHALL log problematic entries and provide guidance for resolution
# Implementation Plan

- [x] 1. Create core CSV format definitions in pyama-core

  - Define ProcessingTraceRecord dataclass and ProcessingCSVLoader class in pyama_core.io.processing_csv
  - Define AnalysisCSVWriter class and validation functions in pyama_core.io.analysis_csv
  - _Requirements: 1.5, 4.2, 4.3_

- [x] 2. Implement FOV range parsing utilities

  - Create fov_parser.py with functions to parse range notation (e.g., "1-4,6,9-20")
  - Implement validation against available FOV indices using 0-based indexing
  - _Requirements: 2.3, 2.4, 2.5_

- [x] 3. Create FOV discovery service

  - Implement FOVDiscoveryService class in services/discovery.py
  - Add method to discover trace CSV files with priority for 'inspected' suffix files
  - Implement FOVInfo dataclass and metadata extraction using ProcessingCSVLoader
  - _Requirements: 1.2, 1.3, 5.1, 5.2_

- [x] 4. Implement data merging service

  - Create MergeService class in services/merge.py with SampleGroup dataclass
  - Implement method to convert processing CSV format to analysis CSV format
  - Add sequential cell ID renumbering (0,1,2,3...) across FOVs within samples
  - Implement time conversion from frame numbers to hours
  - _Requirements: 4.2, 4.3, 4.4, 5.3_

- [x] 5. Create FOV information table widget

  - Implement FOVTable widget in ui/widgets/fov_table.py
  - Create two-column read-only table displaying FOV index and cell count

  - Add method to populate table from FOVInfo list
  - _Requirements: 1.3_

- [x] 6. Create sample grouping table widget

  - Implement SampleTable widget in ui/widgets/sample_table.py
  - Create two-column editable table with Name and FOVs columns
  - Add real-time validation of FOV range notation using fov_parser utilities
  - Implement row selection handling and add/remove functionality
  - _Requirements: 2.1, 2.2, 2.3, 2.6_

- [x] 7. Create statistics display widget

  - Implement StatisticsWidget in ui/widgets/statistics.py
  - Add display for resolved FOV indices, counts, and cell totals
  - Implement update method triggered by sample table selection changes
  - Add error display for invalid FOV ranges
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

- [x] 8. Implement main application window






  - Create MainWindow class in ui/main_window.py
  - Add file browser for selecting processing output directory
  - Integrate FOV table, sample table, and statistics widgets in layout
  - Implement directory selection handling and FOV discovery triggering
  - _Requirements: 1.1, 1.4_

- [x] 9. Add export functionality to main window









  - Implement export button and handler in MainWindow
  - Add validation that all samples have assigned FOVs before export
  - Integrate MergeService to perform data conversion and file writing
  - Add progress indication and success/error messaging through logging
  - _Requirements: 4.1, 4.5, 4.6, 7.3_

- [x] 10. Implement configuration save/load functionality






  - Add MergeConfiguration dataclass for storing sample groupings
  - Implement save/load methods for JSON configuration files
  - Add configuration menu items and handlers to MainWindow
  - Handle missing FOV files gracefully when loading configurations
  - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

- [x] 11. Add comprehensive error handling and logging

  - Implement logging configuration with console output
  - Add error handling for file I/O operations with detailed log messages
  - Implement graceful handling of missing or corrupted CSV files
  - Add validation warnings for data inconsistencies between FOVs
  - _Requirements: 7.1, 7.2, 7.4, 7.5_

- [x] 12. Create main application entry point

  - Implement main.py with Qt application initialization
  - Add multiprocessing support following existing PyAMA-Qt pattern
  - Create application launcher and ensure proper window display
  - _Requirements: All requirements integration_

- [x] 13. Update existing modules to use centralized CSV formats

  - Modify processing module trace_extraction.py to use ProcessingCSVLoader
  - Update visualization module trace_viewer.py to use ProcessingCSVLoader
  - Update analysis module to use AnalysisCSVWriter for data loading
  - _Requirements: 1.5, 4.2, 4.3_

- [ ] 14. Test and debug the complete application
  - Manually test the complete merge workflow with real data
  - Debug any issues found during testing
  - Verify exported CSV files are compatible with analysis module
  - _Requirements: All requirements validation_

# Processing Module

<cite>
**Referenced Files in This Document**   
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py)
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py)
- [workflow_panel.py](file://pyama-qt-slim/src/pyama_qt/app/processing/components/workflow_panel.py)
- [controller.py](file://pyama-qt/src/pyama_qt/processing/controller.py)
- [models.py](file://pyama-qt/src/pyama_qt/processing/models.py)
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py)
- [segmentation.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/segmentation.py)
- [correction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/correction.py)
- [tracking.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/tracking.py)
- [extraction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/extraction.py)
- [tile_interp.py](file://pyama-core/src/pyama_core/processing/background/tile_interp.py)
- [log_std.py](file://pyama-core/src/pyama_core/processing/segmentation/log_std.py)
- [iou.py](file://pyama-core/src/pyama_core/processing/tracking/iou.py)
- [trace.py](file://pyama-core/src/pyama_core/processing/extraction/trace.py)
</cite>

## Table of Contents
1. [Data Ingestion Pipeline](#data-ingestion-pipeline)
2. [Workflow Configuration Interface](#workflow-configuration-interface)
3. [Execution Model and Progress Tracking](#execution-model-and-progress-tracking)
4. [Processing Steps](#processing-steps)
5. [Results Merging and Output Formats](#results-merging-and-output-formats)
6. [Multi-Channel Time-Series Processing Example](#multi-channel-time-series-processing-example)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Architecture Overview](#architecture-overview)

## Data Ingestion Pipeline

The data ingestion pipeline handles raw microscopy data in ND2 and CZI formats through a structured process that begins with file loading and metadata extraction. The `load_microscopy_file` function in `microscopy.py` utilizes the BioImage library to load microscopy files and extract comprehensive metadata including dimensions, channel information, and timepoints. This function returns both the BioImage object and a `MicroscopyMetadata` dataclass containing essential file properties such as height, width, number of frames, FOVs, channels, and acquisition times.

The ingestion process follows a batch-oriented approach where data is extracted from the original microscopy file and converted into NumPy memory-mapped files for efficient processing. The `CopyingService` class manages this extraction, creating separate `.npy` files for each channel and field of view (FOV). These files are organized in a directory structure with subdirectories for each FOV (e.g., `fov_000`, `fov_001`), containing phase contrast and fluorescence channel data. The copying process is optimized to skip already extracted channels, preventing redundant operations when resuming interrupted workflows.

The pipeline supports both phase contrast and multi-channel fluorescence data, with channel selection determined by the processing context. For each selected channel, the system extracts individual frames using the `get_microscopy_frame` function, which handles the indexing of multi-dimensional microscopy data across FOV, channel, and time dimensions. This structured approach ensures that the raw microscopy data is transformed into a standardized format suitable for downstream processing steps.

**Section sources**
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py#L27-L125)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L23-L98)

## Workflow Configuration Interface

The workflow configuration interface provides a comprehensive set of controls for customizing the processing pipeline through channel selection, FOV range specification, and parameter tuning. The `WorkflowPanel` component in the Qt interface presents a user-friendly layout with input and output sections, allowing users to select microscopy files, specify output directories, and configure processing parameters.

Channel selection is implemented through a dual-channel system that distinguishes between phase contrast and fluorescence channels. The phase contrast channel is selected via a dropdown menu, while fluorescence channels support multi-selection through a list widget that displays available channels from the microscopy file. This selection mechanism allows users to process specific subsets of channels, optimizing resource usage when only certain channels contain relevant biological information.

The parameter configuration section enables fine-tuning of processing parameters including FOV range, batch size, and worker count. The FOV range specification allows users to process either all available FOVs or a specific range, which is particularly useful for testing workflows on smaller datasets before full-scale processing. The batch size parameter controls the number of consecutive FOVs processed together, balancing memory usage and processing efficiency. The worker count parameter determines the degree of parallelization, allowing users to optimize performance based on their hardware capabilities.

The underlying `ProcessingConfigModel` maintains the state of these configuration parameters and provides change notifications through Qt signals, ensuring that the UI remains synchronized with the processing state. This model-view architecture separates the configuration logic from the presentation layer, enabling consistent state management across different interface components.

**Section sources**
- [workflow_panel.py](file://pyama-qt-slim/src/pyama_qt/app/processing/components/workflow_panel.py#L20-L145)
- [models.py](file://pyama-qt/src/pyama_qt/processing/models.py#L31-L188)
- [controller.py](file://pyama-qt/src/pyama_qt/processing/controller.py#L333-L603)

## Execution Model and Progress Tracking

The execution model employs a sophisticated parallel processing architecture that combines batch processing with multi-worker parallelization to maximize throughput while maintaining progress tracking. The `run_complete_workflow` function orchestrates the entire processing pipeline, implementing a two-level parallelization strategy where batches of FOVs are processed sequentially, but each batch is processed in parallel across multiple worker processes.

The system uses Python's `ProcessPoolExecutor` with a spawn context to create isolated worker processes, preventing memory leaks and ensuring clean resource management. Each worker process handles a contiguous range of FOVs, with the workload distributed evenly across workers using the `_split_worker_ranges` function. This approach ensures balanced load distribution while maintaining data locality, as consecutive FOVs are typically processed together.

Progress tracking is implemented through a combination of inter-process communication mechanisms. A manager-backed queue facilitates communication between worker processes and the main process, allowing workers to report progress events. A dedicated drainer thread consumes these events and logs progress information, providing real-time feedback on processing status. The `BaseProcessingService` class provides a standardized progress callback mechanism that all processing steps implement, ensuring consistent progress reporting across different stages of the pipeline.

The execution model includes robust error handling and state persistence. If a worker process fails, the system continues processing with remaining workers and reports the failure count. The processing context is merged from successful workers back into the parent context, preserving partial results even if some FOVs fail to process. This fault-tolerant design allows the pipeline to complete as much processing as possible, even in the presence of transient errors.

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)
- [controller.py](file://pyama-qt/src/pyama_qt/processing/controller.py#L333-L603)

## Processing Steps

### Background Correction (Tile Interpolation)
The background correction step implements temporal background subtraction using tile-based interpolation to remove uneven illumination and background fluorescence. The `CorrectionService` processes fluorescence channels by first loading the corresponding segmentation mask, then applying the `correct_bg` function from `tile_interp.py`. This function divides each frame into overlapping tiles, computes median intensities for foreground pixels within each tile, and interpolates a smooth background estimate across the entire image. The interpolated background is then subtracted from the original image to produce background-corrected fluorescence data, which is stored in memory-mapped arrays to minimize memory usage.

### Segmentation (LOG-STD)
The segmentation step applies log-STD thresholding to identify cell regions in phase contrast images. The `SegmentationService` utilizes the `segment_cell` function from `log_std.py`, which computes the logarithm of the standard deviation across spatial scales for each pixel. This log-STD image enhances cell boundaries while suppressing background noise. The algorithm then applies histogram-based thresholding to convert the log-STD image into a binary mask, followed by morphological operations to clean up the segmentation. The resulting binary masks are stored as boolean arrays in memory-mapped files, preserving the temporal dimension for subsequent tracking.

### Tracking (IOU-based)
The tracking step implements cell lineage tracking across timepoints using an IoU-based Hungarian assignment algorithm. The `TrackingService` employs the `track_cell` function from `iou.py`, which extracts connected components from consecutive segmentation frames and builds a cost matrix based on intersection-over-union (IoU) between regions. The Hungarian algorithm solves this assignment problem to maintain consistent cell IDs across frames, creating cell lineages. The tracking process seeds traces only from the first frame, ensuring that newborn cells appearing in later frames are properly integrated into existing lineages through IoU-based matching.

### Feature Extraction (Trace and Feature Modules)
The feature extraction step computes quantitative measurements from fluorescence data using cell masks and tracking information. The `ExtractionService` leverages the `extract_trace` function from `trace.py`, which extracts fluorescence intensity traces for each tracked cell over time. The function first performs IoU-based cell tracking on the labeled segmentation, then extracts mean fluorescence intensity within each cell boundary for every timepoint. Additional features such as cell position and morphology metrics are also computed. The results are organized into a structured DataFrame with columns for frame number, cell ID, position coordinates, and extracted features, which is then saved as CSV files for each FOV and channel combination.

**Section sources**
- [segmentation.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/segmentation.py#L25-L124)
- [correction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/correction.py#L25-L146)
- [tracking.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/tracking.py#L25-L125)
- [extraction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/extraction.py#L25-L132)
- [tile_interp.py](file://pyama-core/src/pyama_core/processing/background/tile_interp.py#L152-L192)
- [log_std.py](file://pyama-core/src/pyama_core/processing/segmentation/log_std.py#L93-L130)
- [iou.py](file://pyama-core/src/pyama_core/processing/tracking/iou.py#L279-L360)
- [trace.py](file://pyama-core/src/pyama_core/processing/extraction/trace.py#L188-L235)

## Results Merging and Output Formats

The results merging process consolidates outputs from parallel workers into a unified results structure, ensuring data integrity and completeness. The `_merge_contexts` function in `pipeline.py` implements a sophisticated merging strategy that combines processing contexts from multiple workers, handling various data types appropriately. For simple values like output directory and time units, the parent context takes precedence. For lists and dictionaries, the function performs union operations with deduplication to combine results from different workers.

The system produces multiple output formats to accommodate different analysis needs. The primary output is a comprehensive `processing_results.yaml` file that contains the merged processing context, including file paths to all generated results, channel configurations, and processing parameters. This YAML file serves as a manifest for the entire processing run, enabling reproducibility and facilitating downstream analysis. The structure includes per-FOV entries with references to phase contrast, segmentation, corrected fluorescence, and trace data files.

In addition to the YAML manifest, the system generates specialized output files for different data types. Segmentation and corrected fluorescence data are stored as NumPy `.npy` files using memory mapping for efficient I/O. Cell tracking results are saved as labeled segmentation arrays, preserving cell identities across frames. Feature extraction outputs are written as CSV files containing time-series data for each cell, with columns for frame number, cell ID, position, and fluorescence intensity. This multi-format approach provides flexibility for different analysis workflows, from immediate visualization to large-scale statistical analysis.

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L71-L140)
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L15-L54)

## Multi-Channel Time-Series Processing Example

A practical example of processing multi-channel time-series data demonstrates the complete workflow from raw microscopy files to analyzed results. Consider a time-lapse experiment with phase contrast and three fluorescence channels (GFP, RFP, DAPI) across 50 FOVs and 100 timepoints. The processing begins with configuring the workflow to select the phase contrast channel and all three fluorescence channels, specifying the full FOV range (0-49), setting batch size to 5, and worker count to 4.

The ingestion phase extracts data for all selected channels, creating memory-mapped files for each FOV. The segmentation step processes phase contrast data to identify cell boundaries, producing binary masks for each timepoint. Background correction is then applied to each fluorescence channel using the corresponding segmentation masks, removing uneven illumination artifacts. The tracking step establishes cell lineages across the 100 timepoints, maintaining consistent cell IDs throughout the time series.

For feature extraction, the system computes fluorescence intensity traces for each cell in all three channels, generating CSV files that contain time-series data with frame numbers, cell positions, and intensity values. The results are merged into a comprehensive YAML manifest that references all output files, enabling downstream analysis of cellular dynamics across multiple channels. This example demonstrates the pipeline's capability to handle complex multi-channel time-series data while maintaining spatial and temporal relationships between cells.

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)
- [controller.py](file://pyama-qt/src/pyama_qt/processing/controller.py#L333-L603)

## Performance Considerations

Performance optimization in the processing module focuses on balancing computational efficiency, memory usage, and I/O throughput through careful parameter tuning. The batch size parameter significantly impacts memory consumption, as larger batches require more memory to store intermediate results. A batch size of 2-5 FOVs is typically optimal, balancing memory usage with processing efficiency. Larger batch sizes may improve throughput on systems with ample RAM but can lead to memory pressure on resource-constrained systems.

The worker count parameter determines the degree of parallelization and should be tuned based on available CPU cores and system memory. Generally, setting the worker count equal to the number of CPU cores provides optimal performance, though reducing it by one or two may improve stability on systems with limited RAM. Each worker requires memory for its processing context and intermediate arrays, so the total memory requirement scales linearly with worker count.

Memory mapping is extensively used throughout the pipeline to minimize RAM usage, allowing the system to process large datasets that exceed available memory. However, this approach increases disk I/O, so using fast storage (SSD) is recommended for optimal performance. The system's design allows for processing datasets much larger than available RAM by leveraging disk-based memory mapping.

For very large datasets, users should consider processing subsets of FOVs or timepoints initially to determine optimal parameter settings before full-scale processing. Monitoring system resource usage during initial runs helps identify bottlenecks and adjust parameters accordingly. The progress tracking system provides valuable feedback on processing speed, enabling users to estimate completion times for large datasets.

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L30-L68)
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)

## Troubleshooting Guide

Common processing failures and their solutions include:

1. **File Not Found Errors**: Ensure the microscopy file path is correct and accessible. Verify that the file format (ND2/CZI) is supported and the file is not corrupted. Check that the output directory has write permissions.

2. **Memory Errors**: Reduce batch size or worker count to decrease memory usage. Close other memory-intensive applications during processing. Consider upgrading system RAM for large datasets.

3. **Channel Selection Issues**: Verify that selected channel indices exist in the microscopy file. Check the channel names in the file metadata to ensure correct indexing. Use the UI's channel selection interface to avoid index errors.

4. **FOV Range Errors**: Ensure the specified FOV range is within the valid range (0 to n_fovs-1). Use -1 for both start and end to process all FOVs.

5. **Progress Stalls**: Check system resources (CPU, disk I/O) for bottlenecks. Verify that the processing is not blocked by antivirus software scanning output files. Consider reducing worker count to reduce I/O contention.

6. **Incomplete Results**: Check the processing log for error messages. Verify that sufficient disk space is available for output files. Restart the workflow to process remaining FOVs, as the system skips already processed data.

The system's fault-tolerant design allows partial completion, so even if some FOVs fail to process, others may complete successfully. Checking the final success count in the processing log helps identify the extent of any issues.

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)
- [controller.py](file://pyama-qt/src/pyama_qt/processing/controller.py#L333-L603)

## Architecture Overview

```mermaid
graph TD
A[Raw Microscopy Data<br/>ND2/CZI] --> B[Data Ingestion]
B --> C[Workflow Configuration]
C --> D[Execution Engine]
D --> E[Processing Steps]
E --> F[Results Merging]
F --> G[Output Formats]
subgraph "Processing Steps"
E1[Background Correction<br/>(Tile Interpolation)]
E2[Segmentation<br/>(LOG-STD)]
E3[Tracking<br/>(IOU-based)]
E4[Feature Extraction<br/>(Trace & Feature)]
end
subgraph "Output Formats"
G1[YAML Manifest]
G2[CSV Traces]
G3[NumPy Arrays]
end
B --> |Channel Selection| C
B --> |FOV Range| C
B --> |Parameters| C
D --> |Batch Size| C
D --> |Worker Count| C
E --> |Progress Tracking| D
F --> |Merged Context| G1
F --> |Cell Traces| G2
F --> |Processed Images| G3
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py)
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L279-L478)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L25-L30)
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py#L11-L24)
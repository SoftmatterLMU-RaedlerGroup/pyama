# Workflow Orchestration

<cite>
**Referenced Files in This Document**   
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py)
- [segmentation.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/segmentation.py)
- [correction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/correction.py)
- [tracking.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/tracking.py)
- [extraction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/extraction.py)
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py)
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py)
- [log_std.py](file://pyama-core/src/pyama_core/processing/segmentation/log_std.py)
- [tile_interp.py](file://pyama-core/src/pyama_core/processing/background/tile_interp.py)
- [iou.py](file://pyama-core/src/pyama_core/processing/tracking/iou.py)
- [trace.py](file://pyama-core/src/pyama_core/processing/extraction/trace.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Pipeline Class Interface](#pipeline-class-interface)
3. [Processing Context Configuration](#processing-context-configuration)
4. [End-to-End Data Flow](#end-to-end-data-flow)
5. [ResultsPathsPerFOV Management](#resultspathsperfov-management)
6. [Code Examples](#code-examples)
7. [Concurrency and Resource Management](#concurrency-and-resource-management)
8. [Error Handling and Monitoring](#error-handling-and-monitoring)
9. [Performance Considerations](#performance-considerations)
10. [Conclusion](#conclusion)

## Introduction
The PyAMA core workflow orchestration system provides a comprehensive pipeline for microscopy image analysis. This documentation details the Pipeline class interface, configuration mechanisms, execution workflow, and integration patterns for the `run_complete_workflow` function. The system is designed to process microscopy data through a series of coordinated steps including copying, segmentation, correction, tracking, and extraction, with robust error handling and progress reporting capabilities.

## Pipeline Class Interface

The workflow orchestration system exposes its primary interface through the `run_complete_workflow` function, which coordinates the complete analysis pipeline. The Pipeline class (implemented as module-level functions) follows a service-oriented architecture with specialized components for each processing step.

```mermaid
classDiagram
class BaseProcessingService {
+str name
+set_progress_reporter(reporter)
+progress_callback(f, t, T, message)
+process_fov(metadata, context, output_dir, fov)
+process_all_fovs(metadata, context, output_dir, fov_start, fov_end)
}
class CopyingService {
+process_fov(metadata, context, output_dir, fov)
}
class SegmentationService {
+process_fov(metadata, context, output_dir, fov)
}
class CorrectionService {
+process_fov(metadata, context, output_dir, fov)
}
class TrackingService {
+process_fov(metadata, context, output_dir, fov)
}
class ExtractionService {
+process_fov(metadata, context, output_dir, fov)
}
BaseProcessingService <|-- CopyingService
BaseProcessingService <|-- SegmentationService
BaseProcessingService <|-- CorrectionService
BaseProcessingService <|-- TrackingService
BaseProcessingService <|-- ExtractionService
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L23-L98)
- [segmentation.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/segmentation.py#L25-L124)
- [correction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/correction.py#L25-L146)
- [tracking.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/tracking.py#L25-L125)
- [extraction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/extraction.py#L25-L132)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)

## Processing Context Configuration

The `ProcessingContext` dataclass serves as the central configuration object for the workflow, carrying parameters, channel specifications, and output paths throughout the processing pipeline. It enables consistent state management across distributed processing steps.

```mermaid
classDiagram
class ProcessingContext {
+Path output_dir
+Channels channels
+dict[int, ResultsPathsPerFOV] results_paths
+dict params
+str time_units
}
class Channels {
+int pc
+list[int] fl
}
class ResultsPathsPerFOV {
+tuple[int, Path] pc
+list[tuple[int, Path]] fl
+tuple[int, Path] seg
+tuple[int, Path] seg_labeled
+list[tuple[int, Path]] fl_corrected
+list[tuple[int, Path]] traces_csv
}
ProcessingContext --> Channels
ProcessingContext --> ResultsPathsPerFOV
```

**Diagram sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L25-L30)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L15-L21)

**Section sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L15-L62)

## End-to-End Data Flow

The workflow orchestrates a multi-stage processing pipeline that transforms raw microscopy data into analyzed outputs. The data flow follows a sequential progression through specialized processing services, with intermediate results persisted to disk and tracked in the processing context.

```mermaid
flowchart TD
A[Raw Microscopy File] --> B[Copying Service]
B --> C[Phase Contrast & Fluorescence .npy files]
C --> D[Segmentation Service]
D --> E[Segmentation Masks .npy]
E --> F[Correction Service]
F --> G[Background Corrected Fluorescence .npy]
G --> H[Tracking Service]
H --> I[Labeled Segmentation .npy]
I --> J[Extraction Service]
J --> K[Traces CSV files]
K --> L[processing_results.yaml]
M[ProcessingContext] --> B
M --> D
M --> F
M --> H
M --> J
M --> L
N[Progress Queue] < --> B
N < --> D
N < --> F
N < --> H
N < --> J
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L23-L98)
- [segmentation.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/segmentation.py#L25-L124)
- [correction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/correction.py#L25-L146)
- [tracking.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/tracking.py#L25-L125)
- [extraction.py](file://pyama-core/src/pyama_core/processing/workflow/services/steps/extraction.py#L25-L132)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

## ResultsPathsPerFOV Management

The `ResultsPathsPerFOV` class plays a critical role in managing per-FOV artifacts throughout the workflow. It maintains references to all intermediate and final output files for each field of view, enabling efficient state tracking and avoiding redundant processing.

```mermaid
classDiagram
class ResultsPathsPerFOV {
+tuple[int, Path] pc
+list[tuple[int, Path]] fl
+tuple[int, Path] seg
+tuple[int, Path] seg_labeled
+list[tuple[int, Path]] fl_corrected
+list[tuple[int, Path]] traces_csv
}
ResultsPathsPerFOV --> "0..*" Path : contains
ProcessingContext --> "1..*" ResultsPathsPerFOV : manages
```

**Diagram sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L15-L21)

**Section sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L15-L62)

## Code Examples

### Pipeline Initialization and Configuration

```mermaid
sequenceDiagram
participant User as "User Code"
participant Pipeline as "run_complete_workflow"
participant Context as "ProcessingContext"
participant Metadata as "MicroscopyMetadata"
User->>Context : Create ProcessingContext(output_dir, channels, params)
User->>Metadata : Load via load_microscopy_file()
User->>Pipeline : run_complete_workflow(metadata, context, fov_start, fov_end, batch_size, n_workers)
Pipeline->>Pipeline : Validate inputs
Pipeline->>Pipeline : Create batches
Pipeline->>Pipeline : Initialize ProcessPoolExecutor
loop For each batch
Pipeline->>Worker : Submit run_single_worker()
end
Worker-->>Pipeline : Return results
Pipeline->>Pipeline : Merge contexts
Pipeline->>User : Return success status
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L25-L30)
- [microscopy.py](file://pyama-core/src/pyama_core/io/microscopy.py#L0-L178)

### Success and Failure State Handling

```mermaid
flowchart TD
A[Start Workflow] --> B{Valid Inputs?}
B --> |No| C[Return False]
B --> |Yes| D[Create Output Directory]
D --> E{Valid FOV Range?}
E --> |No| F[Log Error, Return False]
E --> |Yes| G[Process Batches]
G --> H{Batch Extraction Success?}
H --> |No| I[Log Error, Return False]
H --> |Yes| J[Process in Parallel]
J --> K{All Workers Succeeded?}
K --> |No| L[Log Errors, Continue]
K --> |Yes| M[Merge Results]
M --> N{All FOVs Processed?}
N --> |Yes| O[Write processing_results.yaml]
O --> P[Return True]
N --> |No| Q[Return False]
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

### External Monitoring Integration

```mermaid
sequenceDiagram
participant User as "User Code"
participant Pipeline as "run_complete_workflow"
participant Progress as "Progress Queue"
participant Logger as "Logging System"
User->>Pipeline : Call run_complete_workflow()
Pipeline->>Progress : Create Manager.Queue()
Pipeline->>Logger : Start drainer thread
loop Worker Progress
Worker->>Progress : Put progress event
Progress->>Logger : Drain event
Logger->>Logger : Log progress message
end
Pipeline->>User : Return success status
Pipeline->>Logger : Write processing_results.yaml
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

## Concurrency and Resource Management

The workflow system implements a sophisticated concurrency model using Python's `ProcessPoolExecutor` to parallelize processing across multiple CPU cores. Resource cleanup is handled through context managers and explicit memory mapping disposal.

```mermaid
graph TD
A[Main Process] --> B[ProcessPoolExecutor]
B --> C[Worker Process 1]
B --> D[Worker Process 2]
B --> E[Worker Process N]
F[Manager] --> G[Progress Queue]
A --> F
C --> G
D --> G
E --> G
H[Main Thread] --> I[Drainer Thread]
I --> G
C --> J[Memory Mapped Files]
D --> J
E --> J
style C fill:#f9f,stroke:#333
style D fill:#f9f,stroke:#333
style E fill:#f9f,stroke:#333
style J fill:#bbf,stroke:#333
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

## Error Handling and Monitoring

The system implements comprehensive error handling at multiple levels, from individual FOV processing to batch-level and workflow-level failure detection. Errors are propagated through return values and logged for monitoring purposes.

```mermaid
flowchart TD
A[Process FOV] --> B{Success?}
B --> |Yes| C[Update Context]
B --> |No| D[Capture Exception]
D --> E[Log Error]
E --> F[Return Failure Count]
G[Worker Process] --> H{All FOVs Success?}
H --> |Yes| I[Return Success]
H --> |No| J[Return Partial Success]
K[Main Process] --> L{All Workers Success?}
L --> |Yes| M[Return True]
L --> |No| N[Log Worker Errors]
N --> O[Return False if All Failed]
N --> P[Return True if Some Succeeded]
Q[Final Step] --> R{Write Results YAML}
R --> |Success| S[Return True]
R --> |Failure| T[Log Warning, Return Current Status]
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

## Performance Considerations

The workflow's performance is influenced by several configurable parameters, including batch size and worker count. These settings affect memory usage, disk I/O patterns, and CPU utilization.

```mermaid
graph LR
A[Batch Size] --> B[Memory Usage]
A --> C[Disk I/O Frequency]
A --> D[Worker Load Balance]
E[Worker Count] --> F[CPU Utilization]
E --> G[Memory Pressure]
E --> H[Process Overhead]
I[Large Batch Size] --> J[Higher Memory]
I --> K[Less Frequent I/O]
I --> L[Better Load Balance]
M[Small Batch Size] --> N[Lower Memory]
M --> O[More Frequent I/O]
M --> P[Poorer Load Balance]
Q[High Worker Count] --> R[Higher CPU Use]
Q --> S[Higher Memory Pressure]
Q --> T[Increased Overhead]
U[Low Worker Count] --> V[Lower CPU Use]
U --> W[Lower Memory Pressure]
U --> X[Reduced Overhead]
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L0-L558)

## Conclusion

The PyAMA core workflow orchestration system provides a robust, scalable framework for microscopy image analysis. Through its well-defined `ProcessingContext` configuration, modular service architecture, and sophisticated concurrency model, it enables efficient processing of large microscopy datasets. The system's comprehensive error handling, progress reporting, and result persistence mechanisms make it suitable for both interactive and production environments. By understanding the interactions between the pipeline components and the configuration options available, users can optimize the workflow for their specific hardware and data characteristics.
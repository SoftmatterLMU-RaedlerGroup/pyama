# Service Architecture

<cite>
**Referenced Files in This Document**   
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py)
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py)
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Base Service Class Interface](#base-service-class-interface)
3. [Type System and Data Contracts](#type-system-and-data-contracts)
4. [Service Lifecycle Management](#service-lifecycle-management)
5. [Dependency Injection and Service Composition](#dependency-injection-and-service-composition)
6. [Error Handling Framework](#error-handling-framework)
7. [Custom Service Implementation Example](#custom-service-implementation-example)
8. [Thread Safety and Resource Management](#thread-safety-and-resource-management)
9. [Logging Integration](#logging-integration)
10. [Configuration Validation](#configuration-validation)

## Introduction
The processing service architecture in PyAMA provides a standardized framework for implementing microscopy image analysis workflows. This document details the base classes, type system, and execution patterns that enable consistent, composable, and robust processing services across the application. The architecture is designed to support modular development of analysis steps while ensuring predictable behavior, proper error handling, and efficient resource utilization.

## Base Service Class Interface

The `BaseProcessingService` class serves as the foundation for all processing services in the PyAMA framework. It defines a consistent interface and provides common functionality for progress reporting, error resilience, and batch processing of fields of view (FOVs).

```mermaid
classDiagram
class BaseProcessingService {
+string name
-reporter _progress_reporter
+set_progress_reporter(reporter)
+progress_callback(f, t, T, message)
+process_fov(metadata, context, output_dir, fov)
+process_all_fovs(metadata, context, output_dir, fov_start, fov_end)
}
class CopyingService {
+process_fov(metadata, context, output_dir, fov)
}
BaseProcessingService <|-- CopyingService : "inherits"
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L23-L98)

**Section sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)

## Type System and Data Contracts

The type system in `types.py` standardizes data contracts across services through dataclasses that ensure consistent data exchange and reduce coupling between components. The primary types include `ProcessingContext`, `Channels`, and `ResultsPathsPerFOV`.

```mermaid
classDiagram
class ProcessingContext {
+Path output_dir
+Channels channels
+dict[int, ResultsPathsPerFOV] results_paths
+dict params
+string time_units
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
ProcessingContext --> Channels : "contains"
ProcessingContext --> ResultsPathsPerFOV : "contains"
```

**Diagram sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L9-L21)

**Section sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L25-L30)

## Service Lifecycle Management

The service lifecycle is managed through the `process_all_fovs` method in the base class, which handles range validation, context initialization, and sequential processing of FOVs. The lifecycle includes setup (context validation), execution (per-FOV processing), and implicit teardown (resource cleanup).

```mermaid
sequenceDiagram
participant Client
participant Service
participant Context
Client->>Service : process_all_fovs()
Service->>Service : Validate FOV range
Service->>Context : ensure_context()
Service->>Service : Log start message
loop For each FOV
Service->>Service : process_fov()
Service->>Service : progress_callback()
end
Service->>Service : Log completion message
Service-->>Client : Return
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)

**Section sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)

## Dependency Injection and Service Composition

Dependency injection is implemented through the `set_progress_reporter` method, allowing services to report progress events to external systems without direct coupling. Service composition occurs in the pipeline orchestration, where multiple services are instantiated and chained together to form complete analysis workflows.

```mermaid
sequenceDiagram
participant Pipeline
participant Segmentation
participant Correction
participant Tracking
participant Extraction
Pipeline->>Segmentation : set_progress_reporter()
Pipeline->>Correction : set_progress_reporter()
Pipeline->>Tracking : set_progress_reporter()
Pipeline->>Extraction : set_progress_reporter()
Pipeline->>Segmentation : process_all_fovs()
Pipeline->>Correction : process_all_fovs()
Pipeline->>Tracking : process_all_fovs()
Pipeline->>Extraction : process_all_fovs()
```

**Diagram sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L170-L213)
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L29-L44)

**Section sources**
- [pipeline.py](file://pyama-core/src/pyama_core/processing/workflow/pipeline.py#L170-L213)

## Error Handling Framework

The error handling framework prioritizes resilience, particularly in progress reporting where exceptions are caught and silenced to prevent workflow interruption. Validation is performed at the beginning of processing to catch configuration errors early, and file existence checks prevent redundant processing.

```mermaid
flowchart TD
Start([Start Processing]) --> ValidateRange["Validate FOV Range"]
ValidateRange --> RangeValid{"Range Valid?"}
RangeValid --> |No| ThrowError["Raise ValueError"]
RangeValid --> |Yes| ProcessFOV["Process Each FOV"]
ProcessFOV --> CheckFile["Check Output Exists"]
CheckFile --> FileExists{"File Exists?"}
FileExists --> |Yes| SkipProcessing["Skip Processing"]
FileExists --> |No| ExecuteProcessing["Execute Processing"]
ExecuteProcessing --> ReportProgress["Report Progress"]
ReportProgress --> CatchError["Catch Exception"]
CatchError --> Continue["Continue Processing"]
SkipProcessing --> NextFOV["Next FOV"]
Continue --> NextFOV
NextFOV --> MoreFOVs{"More FOVs?"}
MoreFOVs --> |Yes| ProcessFOV
MoreFOVs --> |No| Complete["Log Completion"]
Complete --> End([End])
ThrowError --> End
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L28-L98)

**Section sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)

## Custom Service Implementation Example

To implement a custom service, inherit from `BaseProcessingService` and override the `process_fov` method. The service automatically inherits progress reporting, context management, and batch processing capabilities from the base class.

```mermaid
classDiagram
class BaseProcessingService {
<<abstract>>
+process_fov(metadata, context, output_dir, fov)
}
class CustomService {
+process_fov(metadata, context, output_dir, fov)
}
BaseProcessingService <|-- CustomService
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L15-L83)

**Section sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L46-L53)

## Thread Safety and Resource Management

The architecture ensures thread safety through stateless service instances and immutable data contracts. Resource disposal is handled explicitly through context managers and manual cleanup of memory-mapped files, preventing resource leaks during long-running operations.

```mermaid
flowchart TD
Start([Service Execution]) --> CreateMemmap["Create Memory-Mapped File"]
CreateMemmap --> ProcessFrames["Process Frames"]
ProcessFrames --> FlushData["Flush Data to Disk"]
FlushData --> DeleteMemmap["Delete Memory-Mapped Reference"]
DeleteMemmap --> Cleanup["Cleanup Resources"]
Cleanup --> End([Complete])
style CreateMemmap fill:#f9f,stroke:#333
style DeleteMemmap fill:#f9f,stroke:#333
```

**Diagram sources**
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L28-L98)

**Section sources**
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L28-L98)

## Logging Integration

Logging is integrated throughout the service lifecycle, providing visibility into processing progress and status. Log messages include contextual information such as FOV number, processing step, and progress percentage, enabling detailed monitoring and debugging.

```mermaid
sequenceDiagram
participant Service
participant Logger
participant User
Service->>Logger : info("Starting Copy for FOVs 0-5")
Service->>Logger : info("FOV 0 : Processing PC channel 0")
Service->>Logger : info("FOV 0 : Copying PC channel 0...")
Service->>Logger : info("FOV 0 copy completed")
Service->>Logger : info("Copy completed successfully for FOVs 0-5")
Logger->>User : Display log messages
```

**Diagram sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)
- [copying.py](file://pyama-core/src/pyama_core/processing/workflow/services/copying.py#L28-L98)

**Section sources**
- [base.py](file://pyama-core/src/pyama_core/processing/workflow/services/base.py#L55-L83)

## Configuration Validation

Configuration validation is performed through the `ensure_context` function, which guarantees that all required fields are initialized with appropriate default values. This prevents null pointer exceptions and ensures consistent behavior across services regardless of input completeness.

```mermaid
flowchart TD
Start([ensure_context]) --> CheckNull{"Context is None?"}
CheckNull --> |Yes| CreateNew["Create New Context"]
CheckNull --> |No| CheckChannels{"Channels is None?"}
CheckChannels --> |Yes| InitChannels["Initialize Channels"]
CheckChannels --> |No| CheckResults{"Results Paths is None?"}
CheckResults --> |Yes| InitResults["Initialize Results Paths"]
CheckResults --> |No| CheckParams{"Params is None?"}
CheckParams --> |Yes| InitParams["Initialize Params"]
CheckParams --> |No| ReturnContext["Return Context"]
CreateNew --> ReturnContext
InitChannels --> ReturnContext
InitResults --> ReturnContext
InitParams --> ReturnContext
```

**Diagram sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L37-L54)

**Section sources**
- [types.py](file://pyama-core/src/pyama_core/processing/workflow/services/types.py#L37-L54)
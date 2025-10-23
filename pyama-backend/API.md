# PyAMA Backend API Design

## Overview

This document describes the REST API for PyAMA Backend, which provides processing and analysis functionality for microscopy image analysis. The API is built with FastAPI and follows RESTful principles.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication. Future versions may implement API key or JWT-based authentication.

## API Endpoints

### Processing Endpoints

#### 1. Load Microscopy File Metadata

**POST** `/processing/load-metadata`

Load metadata from a microscopy file (ND2 or CZI format).

**Request Body:**
```json
{
  "file_path": "/path/to/file.nd2"
}
```

**Response:**
```json
{
  "success": true,
  "metadata": {
    "n_fovs": 100,
    "n_frames": 50,
    "n_channels": 4,
    "channel_names": ["Phase", "GFP", "RFP", "DAPI"],
    "time_units": "hours",
    "pixel_size_um": 0.65
  }
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Failed to load file: File not found"
}
```

---

#### 2. Get Available Features

**GET** `/processing/features`

Get list of available features for phase contrast and fluorescence channels.

**Response:**
```json
{
  "phase_features": [
    "area",
    "circularity",
    "eccentricity",
    "perimeter"
  ],
  "fluorescence_features": [
    "intensity_total",
    "intensity_mean",
    "intensity_max",
    "intensity_variance"
  ]
}
```

---

#### 3. Start Processing Workflow

**POST** `/processing/workflow/start`

Start a complete processing workflow with specified parameters.

**Request Body:**
```json
{
  "microscopy_path": "/path/to/file.nd2",
  "output_dir": "/path/to/output",
  "channels": {
    "phase": {
      "channel": 0,
      "features": ["area", "circularity"]
    },
    "fluorescence": [
      {
        "channel": 1,
        "features": ["intensity_total", "intensity_mean"]
      },
      {
        "channel": 2,
        "features": ["intensity_total"]
      }
    ]
  },
  "parameters": {
    "fov_start": 0,
    "fov_end": 99,
    "batch_size": 2,
    "n_workers": 2
  }
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "job_123456",
  "message": "Workflow started successfully"
}
```

**Error Response:**
```json
{
  "success": false,
  "error": "Invalid parameters: fov_end must be less than n_fovs"
}
```

---

#### 4. Get Workflow Status

**GET** `/processing/workflow/status/{job_id}`

Get the current status of a running workflow.

**Response:**
```json
{
  "job_id": "job_123456",
  "status": "running",
  "progress": {
    "current_fov": 45,
    "total_fovs": 100,
    "percentage": 45.0
  },
  "message": "Processing FOV 45/100"
}
```

**Status Values:**
- `pending`: Job is queued but not started
- `running`: Job is currently executing
- `completed`: Job completed successfully
- `failed`: Job failed with an error
- `cancelled`: Job was cancelled by user

---

#### 5. Cancel Workflow

**POST** `/processing/workflow/cancel/{job_id}`

Cancel a running workflow.

**Response:**
```json
{
  "success": true,
  "message": "Workflow cancelled successfully"
}
```

---

#### 6. Get Workflow Results

**GET** `/processing/workflow/results/{job_id}`

Get the results of a completed workflow.

**Response:**
```json
{
  "success": true,
  "output_dir": "/path/to/output",
  "results_file": "/path/to/output/processing_results.yaml",
  "traces": [
    "/path/to/output/fov_000/fov_000_traces.csv",
    "/path/to/output/fov_001/fov_001_traces.csv"
  ]
}
```

---

#### 7. Merge Processing Results

**POST** `/processing/merge`

Merge processing results with sample definitions.

**Request Body:**
```json
{
  "sample_yaml": "/path/to/samples.yaml",
  "processing_results_yaml": "/path/to/processing_results.yaml",
  "output_dir": "/path/to/output"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Merge completed successfully",
  "output_dir": "/path/to/output",
  "merged_csv": "/path/to/output/merged_traces.csv"
}
```

---

### Analysis Endpoints

#### 8. Get Available Models

**GET** `/analysis/models`

Get list of available fitting models.

**Response:**
```json
{
  "models": [
    {
      "name": "trivial",
      "description": "Trivial model for testing",
      "parameters": [
        {
          "name": "a",
          "default": 1.0,
          "bounds": [0.0, 10.0]
        },
        {
          "name": "b",
          "default": 0.0,
          "bounds": [-5.0, 5.0]
        }
      ]
    },
    {
      "name": "maturation",
      "description": "Maturation model",
      "parameters": [
        {
          "name": "k_maturation",
          "default": 0.1,
          "bounds": [0.0, 1.0]
        },
        {
          "name": "k_degradation",
          "default": 0.05,
          "bounds": [0.0, 1.0]
        }
      ]
    }
  ]
}
```

---

#### 9. Load Trace Data

**POST** `/analysis/load-traces`

Load trace data from a CSV file.

**Request Body:**
```json
{
  "csv_path": "/path/to/traces.csv"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "n_cells": 150,
    "n_timepoints": 50,
    "time_units": "hours",
    "columns": ["cell_001", "cell_002", "cell_003", ...]
  }
}
```

---

#### 10. Start Fitting

**POST** `/analysis/fitting/start`

Start fitting analysis on trace data.

**Request Body:**
```json
{
  "csv_path": "/path/to/traces.csv",
  "model_type": "maturation",
  "model_params": {
    "k_maturation": 0.1,
    "k_degradation": 0.05
  },
  "model_bounds": {
    "k_maturation": [0.0, 1.0],
    "k_degradation": [0.0, 1.0]
  }
}
```

**Response:**
```json
{
  "success": true,
  "job_id": "fit_123456",
  "message": "Fitting started successfully"
}
```

---

#### 11. Get Fitting Status

**GET** `/analysis/fitting/status/{job_id}`

Get the current status of a fitting job.

**Response:**
```json
{
  "job_id": "fit_123456",
  "status": "running",
  "progress": {
    "current_cell": 75,
    "total_cells": 150,
    "percentage": 50.0
  },
  "message": "Fitting cell 75/150"
}
```

---

#### 12. Cancel Fitting

**POST** `/analysis/fitting/cancel/{job_id}`

Cancel a running fitting job.

**Response:**
```json
{
  "success": true,
  "message": "Fitting cancelled successfully"
}
```

---

#### 13. Get Fitting Results

**GET** `/analysis/fitting/results/{job_id}`

Get the results of a completed fitting job.

**Response:**
```json
{
  "success": true,
  "results_file": "/path/to/traces_fitted_maturation.csv",
  "summary": {
    "total_cells": 150,
    "successful_fits": 145,
    "failed_fits": 5,
    "mean_r_squared": 0.92
  },
  "results": [
    {
      "cell_id": "cell_001",
      "model_type": "maturation",
      "success": true,
      "r_squared": 0.95,
      "fitted_params": {
        "k_maturation": 0.12,
        "k_degradation": 0.06
      }
    },
    ...
  ]
}
```

---

## Data Models

### Channel Selection

```typescript
interface ChannelSelection {
  channel: number;
  features: string[];
}
```

### Channels Configuration

```typescript
interface Channels {
  phase: ChannelSelection | null;
  fluorescence: ChannelSelection[];
}
```

### Workflow Parameters

```typescript
interface WorkflowParameters {
  fov_start: number;
  fov_end: number;
  batch_size: number;
  n_workers: number;
}
```

### Fitting Request

```typescript
interface FittingRequest {
  csv_path: string;
  model_type: string;
  model_params: Record<string, number>;
  model_bounds: Record<string, [number, number]>;
}
```

### Job Status

```typescript
interface JobStatus {
  job_id: string;
  status: "pending" | "running" | "completed" | "failed" | "cancelled";
  progress?: {
    current: number;
    total: number;
    percentage: number;
  };
  message: string;
}
```

## Error Handling

All endpoints return consistent error responses:

```json
{
  "success": false,
  "error": "Error message describing what went wrong",
  "error_code": "ERROR_CODE"
}
```

Common error codes:
- `FILE_NOT_FOUND`: Requested file does not exist
- `INVALID_PARAMETERS`: Request parameters are invalid
- `PROCESSING_ERROR`: Error during processing
- `JOB_NOT_FOUND`: Job ID does not exist
- `JOB_ALREADY_COMPLETED`: Job has already completed
- `INTERNAL_ERROR`: Unexpected server error

## WebSocket Support (Future)

For real-time progress updates, WebSocket endpoints may be added:

- `ws://localhost:8000/ws/workflow/{job_id}` - Workflow progress updates
- `ws://localhost:8000/ws/fitting/{job_id}` - Fitting progress updates

## Rate Limiting

Currently no rate limiting is implemented. Future versions may add rate limiting based on:
- Number of concurrent jobs per user
- API request rate per minute

## File Upload (Future)

For handling large microscopy files, file upload endpoints may be added:

- `POST /processing/upload` - Upload microscopy file
- `GET /processing/files` - List uploaded files
- `DELETE /processing/files/{file_id}` - Delete uploaded file

## Notes

1. All file paths in requests should be absolute paths accessible by the backend server
2. The backend processes jobs asynchronously - use the job_id to track status
3. Results are saved to the specified output directories
4. Cancelled jobs may leave partial results in the output directory
5. The API follows the same processing pipeline as the Qt GUI application

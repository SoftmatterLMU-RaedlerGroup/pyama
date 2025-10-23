# PyAMA Backend

FastAPI backend for PyAMA microscopy image analysis.

## Overview

This backend provides REST API endpoints for:
- **Processing**: Load microscopy files, configure channels/features, run complete workflows, merge results
- **Analysis**: Load trace data, configure fitting models, run fitting analysis

## Architecture

The backend is designed to:
1. Accept REST API requests from a Next.js frontend
2. Execute long-running processing and analysis jobs asynchronously
3. Provide job status tracking and cancellation
4. Return results and metadata

## Key Design Decisions

### 1. Asynchronous Job Processing

All long-running operations (workflow execution, fitting) are handled asynchronously:
- Client submits a job and receives a `job_id`
- Client polls for status using the `job_id`
- Client can cancel jobs using the `job_id`
- Results are retrieved after completion

### 2. File Path Handling

Currently, the API expects absolute file paths. This means:
- The backend must have access to the same filesystem as the frontend
- Future versions may support file upload/download

### 3. No Authentication (Initial Version)

The initial version does not include authentication. This is suitable for:
- Local development
- Single-user deployments
- Trusted network environments

Future versions will add:
- API key authentication
- JWT-based authentication
- User management

### 4. Job Management

Jobs are tracked in-memory initially. For production, consider:
- Redis for job queue management
- PostgreSQL for job persistence
- Celery for distributed task processing

## API Design Highlights

### Processing Endpoints

1. **Load Metadata** - Extract channel information from microscopy files
2. **Get Features** - List available features for each channel type
3. **Start Workflow** - Begin processing with full configuration
4. **Status/Cancel/Results** - Manage workflow execution

### Analysis Endpoints

1. **Get Models** - List available fitting models with parameters
2. **Load Traces** - Load CSV trace data
3. **Start Fitting** - Begin fitting analysis
4. **Status/Cancel/Results** - Manage fitting execution

## Implementation Plan

### Phase 1: Core API Structure
- [ ] Set up FastAPI project structure
- [ ] Implement request/response models
- [ ] Add basic error handling

### Phase 2: Processing Endpoints
- [ ] Implement metadata loading
- [ ] Implement workflow execution
- [ ] Add job tracking and status

### Phase 3: Analysis Endpoints
- [ ] Implement model listing
- [ ] Implement trace loading
- [ ] Implement fitting execution

### Phase 4: Job Management
- [ ] Add job persistence
- [ ] Implement cancellation
- [ ] Add progress tracking

### Phase 5: Testing & Documentation
- [ ] Add unit tests
- [ ] Add integration tests
- [ ] Generate OpenAPI documentation

## Dependencies

- FastAPI - Web framework
- Uvicorn - ASGI server
- Pydantic - Data validation
- pyama-core - Core processing logic (from workspace)

## Development

```bash
# Install dependencies
uv sync --all-extras

# Run development server
uv run python -m pyama_backend

# Or use uvicorn directly
uvicorn pyama_backend.main:app --reload

# Run tests
pytest
```

## Testing the API

Once the server is running, you can test the load metadata endpoint:

```bash
# Using curl
curl -X POST "http://localhost:8000/api/v1/processing/load-metadata" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/your/file.nd2"}'

# Or use the test script (update the file path first)
python test_load_metadata.py
```

## API Documentation

Once the server is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Next Steps

1. Review the API design in `API.md`
2. Discuss any changes or additions needed
3. Begin implementation based on agreed design

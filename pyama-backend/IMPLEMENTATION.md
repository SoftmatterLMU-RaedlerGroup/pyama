# Load Metadata API Implementation

## Summary

Implemented the `/api/v1/processing/load-metadata` endpoint for loading microscopy file metadata.

## Files Created

### 1. `src/pyama_backend/main.py`
- Main FastAPI application
- CORS middleware configuration
- Router registration
- Health check endpoint

### 2. `src/pyama_backend/api/processing.py`
- `LoadMetadataRequest` - Request model for file path
- `MicroscopyMetadataResponse` - Response model for metadata
- `LoadMetadataResponse` - Wrapper response with success/error
- `load_metadata()` endpoint - Main implementation

### 3. `src/pyama_backend/__main__.py`
- Entry point for running the server with uvicorn

### 4. `test_load_metadata.py`
- Test script for manual testing

## API Endpoint

**POST** `/api/v1/processing/load-metadata`

### Request
```json
{
  "file_path": "/path/to/file.nd2"
}
```

### Success Response
```json
{
  "success": true,
  "metadata": {
    "file_path": "/path/to/file.nd2",
    "base_name": "file",
    "file_type": "nd2",
    "height": 2048,
    "width": 2048,
    "n_frames": 50,
    "n_fovs": 100,
    "n_channels": 4,
    "timepoints": [0.0, 1.0, 2.0, ...],
    "channel_names": ["Phase", "GFP", "RFP", "DAPI"],
    "dtype": "uint16"
  }
}
```

### Error Response
```json
{
  "success": false,
  "error": "File not found: /path/to/file.nd2"
}
```

## Features

1. **File Validation**
   - Checks if file exists
   - Validates file extension (.nd2 or .czi)

2. **Error Handling**
   - Returns structured error responses
   - Logs errors for debugging

3. **Metadata Extraction**
   - Uses `pyama_core.io.load_microscopy_file()`
   - Extracts all metadata fields
   - Converts to JSON-serializable format

## Usage

### Start the Server
```bash
cd pyama-backend
uv run python -m pyama_backend
```

### Test with curl
```bash
curl -X POST "http://localhost:8000/api/v1/processing/load-metadata" \
  -H "Content-Type: application/json" \
  -d '{"file_path": "/path/to/your/file.nd2"}'
```

### Test with Python
```python
import requests

response = requests.post(
    "http://localhost:8000/api/v1/processing/load-metadata",
    json={"file_path": "/path/to/your/file.nd2"}
)

result = response.json()
if result["success"]:
    print(f"Channels: {result['metadata']['channel_names']}")
    print(f"FOVs: {result['metadata']['n_fovs']}")
else:
    print(f"Error: {result['error']}")
```

## Next Steps

1. Test with actual ND2/CZI files
2. Implement remaining processing endpoints
3. Add unit tests
4. Add integration tests

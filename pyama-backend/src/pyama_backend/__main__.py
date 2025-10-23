"""Entry point for running the FastAPI server."""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "pyama_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

"""Main FastAPI application for PyAMA Backend."""

import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyama_backend.api import processing, analysis
from pyama_backend.jobs import JobManager
from pyama_core.plugin.loader import load_plugins

logger = logging.getLogger(__name__)

# Load plugins at startup
logger.info("Loading plugins...")
try:
    plugin_scanner = load_plugins()
    logger.info(f"Successfully loaded {len(plugin_scanner.plugins)} plugin(s)")
except Exception as e:
    logger.warning(f"Failed to load plugins: {e}")

# Create global job manager
job_manager = JobManager()

app = FastAPI(
    title="PyAMA Backend API",
    description="FastAPI backend for microscopy image analysis",
    version="0.1.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify actual frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(processing.router, prefix="/api/v1/processing", tags=["processing"])
app.include_router(analysis.router, prefix="/api/v1/analysis", tags=["analysis"])


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "PyAMA Backend API", "version": "0.1.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


def main() -> None:
    """Run the FastAPI server."""
    uvicorn.run(
        "pyama_backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )

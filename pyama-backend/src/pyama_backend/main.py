"""Main FastAPI application for PyAMA Backend."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pyama_backend.api import processing, analysis

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

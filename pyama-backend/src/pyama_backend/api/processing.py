"""Processing API endpoints."""

import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from pyama_core.io import MicroscopyMetadata, load_microscopy_file

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================


class LoadMetadataRequest(BaseModel):
    """Request model for loading microscopy metadata."""

    file_path: str = Field(..., description="Path to microscopy file (ND2 or CZI)")


class MicroscopyMetadataResponse(BaseModel):
    """Response model for microscopy metadata."""

    file_path: str
    base_name: str
    file_type: str
    height: int
    width: int
    n_frames: int
    n_fovs: int
    n_channels: int
    timepoints: list[float]
    channel_names: list[str]
    dtype: str

    @classmethod
    def from_metadata(cls, metadata: MicroscopyMetadata) -> "MicroscopyMetadataResponse":
        """Create response from MicroscopyMetadata."""
        return cls(
            file_path=str(metadata.file_path),
            base_name=metadata.base_name,
            file_type=metadata.file_type,
            height=metadata.height,
            width=metadata.width,
            n_frames=metadata.n_frames,
            n_fovs=metadata.n_fovs,
            n_channels=metadata.n_channels,
            timepoints=metadata.timepoints,
            channel_names=metadata.channel_names,
            dtype=metadata.dtype,
        )


class LoadMetadataResponse(BaseModel):
    """Response model for load metadata endpoint."""

    success: bool
    metadata: MicroscopyMetadataResponse | None = None
    error: str | None = None


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/load-metadata", response_model=LoadMetadataResponse)
async def load_metadata(request: LoadMetadataRequest) -> LoadMetadataResponse:
    """Load metadata from a microscopy file (ND2 or CZI format).

    Args:
        request: Request containing file path

    Returns:
        Response with metadata or error message
    """
    file_path = Path(request.file_path)

    # Validate file exists
    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        return LoadMetadataResponse(
            success=False,
            error=f"File not found: {file_path}",
        )

    # Validate file extension
    if file_path.suffix.lower() not in [".nd2", ".czi"]:
        logger.error("Unsupported file type: %s", file_path.suffix)
        return LoadMetadataResponse(
            success=False,
            error=f"Unsupported file type: {file_path.suffix}. Supported types: .nd2, .czi",
        )

    try:
        # Load microscopy file
        logger.info("Loading microscopy file: %s", file_path)
        _, metadata = load_microscopy_file(file_path)

        # Convert to response model
        metadata_response = MicroscopyMetadataResponse.from_metadata(metadata)

        logger.info(
            "Successfully loaded metadata: %d channels, %d FOVs, %d frames",
            metadata.n_channels,
            metadata.n_fovs,
            metadata.n_frames,
        )

        return LoadMetadataResponse(
            success=True,
            metadata=metadata_response,
        )

    except Exception as e:
        logger.exception("Failed to load microscopy file: %s", file_path)
        return LoadMetadataResponse(
            success=False,
            error=f"Failed to load file: {str(e)}",
        )

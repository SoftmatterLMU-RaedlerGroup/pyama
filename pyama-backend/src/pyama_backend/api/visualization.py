"""Visualization API endpoints."""

import logging
import numpy as np
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from pyama_core.visualization import VisualizationCache

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# MODELS
# =============================================================================


class VisualizationInitRequest(BaseModel):
    """Request model for initializing visualization data."""

    output_dir: str = Field(..., description="Workflow output directory")
    fov_id: int = Field(..., ge=0, description="FOV identifier")
    channels: list[str] = Field(..., description="Channel keys to load (e.g., pc, 1, 2)")
    data_types: list[Literal["image", "seg"]] = Field(
        default_factory=lambda: ["image", "seg"],
        description="Artifact types to include",
    )
    force_rebuild: bool = Field(False, description="Rebuild cached uint8 stacks")


class ChannelMeta(BaseModel):
    """Per-channel metadata for visualization."""

    channel: str
    dtype: str
    shape: tuple[int, ...]
    n_frames: int
    vmin: int
    vmax: int
    path: str


class VisualizationInitResponse(BaseModel):
    """Response model for visualization initialization."""

    success: bool
    fov_id: int
    channels: list[ChannelMeta] = []
    traces_csv: Optional[str] = None
    error: Optional[str] = None


class VisualizationFrameRequest(BaseModel):
    """Request frames from a cached stack."""

    cached_path: str = Field(..., description="Path to cached uint8 stack")
    channel: str = Field(..., description="Channel identifier")
    frame: Optional[int] = Field(None, ge=0, description="Single frame index")
    frame_start: Optional[int] = Field(None, ge=0, description="Start frame index (inclusive)")
    frame_end: Optional[int] = Field(None, ge=0, description="End frame index (inclusive)")


class VisualizationFrameResponse(BaseModel):
    """Response containing requested frame data."""

    success: bool
    channel: str
    frames: list[list[list[int]]] = []
    error: Optional[str] = None


# =============================================================================
# HELPERS
# =============================================================================


def _locate_fov_artifacts(output_dir: Path, fov_id: int) -> dict[str, Path]:
    """Locate expected artifacts for a FOV."""
    fov_dir = output_dir / f"fov_{fov_id:03d}"
    artifacts: dict[str, Path] = {}

    # Phase contrast
    pc_path = fov_dir / "pc.npy"
    if pc_path.exists():
        artifacts["pc"] = pc_path

    # Fluorescence channels (fl_{id}.npy)
    for fl_file in fov_dir.glob("fl_*.npy"):
        channel_id = fl_file.stem.split("_")[-1]
        artifacts[channel_id] = fl_file

    # Segmentation
    seg_path = fov_dir / "seg.npy"
    if seg_path.exists():
        artifacts["seg"] = seg_path

    seg_labeled = fov_dir / "seg_labeled.npy"
    if seg_labeled.exists():
        artifacts["seg_labeled"] = seg_labeled

    # Traces
    traces_csv = fov_dir / f"fov_{fov_id:03d}_traces.csv"
    if traces_csv.exists():
        artifacts["traces_csv"] = traces_csv

    return artifacts


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.post("/visualization/init", response_model=VisualizationInitResponse)
async def visualization_init(request: VisualizationInitRequest) -> VisualizationInitResponse:
    """Prepare cached uint8 stacks and return metadata for requested channels."""

    try:
        output_dir = Path(request.output_dir)
        logger.info(
            "Initializing visualization for fov=%d (channels=%s, data_types=%s, output_dir=%s)",
            request.fov_id,
            request.channels,
            request.data_types,
            output_dir,
        )

        if not output_dir.exists():
            error_msg = f"Output directory not found: {output_dir}"
            logger.error(error_msg)
            return VisualizationInitResponse(
                success=False,
                fov_id=request.fov_id,
                error=error_msg,
            )

        if not output_dir.is_dir():
            error_msg = f"Output directory is not a directory: {output_dir}"
            logger.error(error_msg)
            return VisualizationInitResponse(
                success=False,
                fov_id=request.fov_id,
                error=error_msg,
            )

        fov_dir = output_dir / f"fov_{request.fov_id:03d}"
        if not fov_dir.exists():
            error_msg = f"FOV directory not found: {fov_dir}"
            logger.error(error_msg)
            return VisualizationInitResponse(
                success=False,
                fov_id=request.fov_id,
                error=error_msg,
            )

        artifacts = _locate_fov_artifacts(output_dir, request.fov_id)
        if not artifacts:
            error_msg = f"No artifacts found for FOV {request.fov_id} in {output_dir}"
            logger.error(error_msg)
            return VisualizationInitResponse(
                success=False,
                fov_id=request.fov_id,
                error=error_msg,
            )

        channels_meta: list[ChannelMeta] = []
        missing_channels: list[str] = []
        cache = VisualizationCache()

        for channel in request.channels:
            source_path = artifacts.get(channel)
            if not source_path:
                logger.warning("Channel %s not found for FOV %d", channel, request.fov_id)
                missing_channels.append(channel)
                continue

            cached = cache.get_or_build_uint8(
                source_path,
                channel,
                force_rebuild=request.force_rebuild,
            )

            channels_meta.append(
                ChannelMeta(
                    channel=channel,
                    dtype="uint8",
                    shape=cached.shape,
                    n_frames=cached.n_frames,
                    vmin=cached.vmin,
                    vmax=cached.vmax,
                    path=str(cached.path),
                )
            )

        traces_csv = artifacts.get("traces_csv")
        if not channels_meta:
            missing = f" Missing: {', '.join(missing_channels)}" if missing_channels else ""
            error_msg = (
                f"No visualization channels available for FOV {request.fov_id}.{missing}"
            )
            logger.error(error_msg)
            return VisualizationInitResponse(
                success=False,
                fov_id=request.fov_id,
                channels=[],
                traces_csv=str(traces_csv) if traces_csv else None,
                error=error_msg,
            )

        return VisualizationInitResponse(
            success=True,
            fov_id=request.fov_id,
            channels=channels_meta,
            traces_csv=str(traces_csv) if traces_csv else None,
        )
    except Exception as exc:
        logger.exception("Failed to initialize visualization")
        return VisualizationInitResponse(
            success=False,
            fov_id=request.fov_id,
            error=str(exc),
        )


@router.post("/visualization/frame", response_model=VisualizationFrameResponse)
async def visualization_frame(request: VisualizationFrameRequest) -> VisualizationFrameResponse:
    """Return a frame or frame slice from a cached uint8 stack."""

    try:
        cache = VisualizationCache()
        cached_path = Path(request.cached_path)
        if not cached_path.exists():
            return VisualizationFrameResponse(
                success=False,
                channel=request.channel,
                error=f"Cached path not found: {cached_path}",
            )

        frames: list[np.ndarray]
        if request.frame is not None:
            frame_data = cache.load_frame(cached_path, request.frame)
            frames = [frame_data]
        else:
            if request.frame_start is None or request.frame_end is None:
                return VisualizationFrameResponse(
                    success=False,
                    channel=request.channel,
                    error="frame or (frame_start and frame_end) must be provided",
                )
            slice_data = cache.load_slice(cached_path, request.frame_start, request.frame_end)
            frames = list(slice_data) if slice_data.ndim == 3 else [slice_data]

        # Serialize to lists for JSON
        frame_payload = [frame.tolist() for frame in frames]

        return VisualizationFrameResponse(
            success=True,
            channel=request.channel,
            frames=frame_payload,
        )
    except Exception as exc:
        logger.exception("Failed to load visualization frame")
        return VisualizationFrameResponse(
            success=False,
            channel=request.channel,
            error=str(exc),
        )

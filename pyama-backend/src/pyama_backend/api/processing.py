"""Processing API endpoints."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from pyama_core.io import MicroscopyMetadata, load_microscopy_file
from pyama_core.processing.extraction.features import (
    list_phase_features,
    list_fluorescence_features,
)
from pyama_core.types.processing import ChannelSelection, Channels

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
    def from_metadata(
        cls, metadata: MicroscopyMetadata
    ) -> "MicroscopyMetadataResponse":
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


class FeaturesResponse(BaseModel):
    """Response model for available features endpoint."""

    phase_features: list[str]
    fluorescence_features: list[str]


# =============================================================================
# WORKFLOW MODELS
# =============================================================================


class ChannelSelectionRequest(BaseModel):
    """Request model for channel selection."""

    channel: int = Field(..., description="Channel index")
    features: list[str] = Field(..., description="List of features to extract")


class WorkflowChannelsRequest(BaseModel):
    """Request model for workflow channels configuration."""

    phase: Optional[ChannelSelectionRequest] = Field(
        None, description="Phase channel configuration"
    )
    fluorescence: list[ChannelSelectionRequest] = Field(
        default_factory=list, description="Fluorescence channel configurations"
    )


class WorkflowParametersRequest(BaseModel):
    """Request model for workflow parameters."""

    fov_start: int = Field(0, description="Starting FOV index")
    fov_end: int = Field(..., description="Ending FOV index")
    batch_size: int = Field(2, description="Batch size for processing")
    n_workers: int = Field(2, description="Number of worker threads")


class StartWorkflowRequest(BaseModel):
    """Request model for starting a workflow."""

    microscopy_path: str = Field(..., description="Path to microscopy file")
    output_dir: str = Field(..., description="Output directory for results")
    channels: WorkflowChannelsRequest = Field(..., description="Channel configuration")
    parameters: WorkflowParametersRequest = Field(
        ..., description="Workflow parameters"
    )


class StartWorkflowResponse(BaseModel):
    """Response model for starting a workflow."""

    success: bool
    job_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response model for job status."""

    job_id: str
    status: str
    progress: Optional[dict] = None
    message: str


class CancelWorkflowResponse(BaseModel):
    """Response model for cancelling a workflow."""

    success: bool
    message: str


class WorkflowResultsResponse(BaseModel):
    """Response model for workflow results."""

    success: bool
    output_dir: Optional[str] = None
    results_file: Optional[str] = None
    traces: list[str] = []
    error: Optional[str] = None


class MergeRequest(BaseModel):
    """Request model for merging processing results."""

    sample_yaml: str = Field(..., description="Path to samples YAML file")
    processing_results_yaml: str = Field(
        ..., description="Path to processing results YAML file"
    )
    output_dir: str = Field(..., description="Output directory for merged files")


class MergeResponse(BaseModel):
    """Response model for merge endpoint."""

    success: bool
    message: str = ""
    output_dir: Optional[str] = None
    merged_files: list[str] = []
    error: Optional[str] = None


# =============================================================================
# FILE EXPLORER MODELS
# =============================================================================


class FileItem(BaseModel):
    """Model for a file or directory item."""

    name: str
    path: str
    is_directory: bool
    is_file: bool
    size_bytes: Optional[int] = None
    modified_time: Optional[str] = None
    extension: Optional[str] = None


class DirectoryListingRequest(BaseModel):
    """Request model for listing directory contents."""

    directory_path: str = Field(..., description="Path to directory to list")
    include_hidden: bool = Field(
        False, description="Include hidden files and directories"
    )
    filter_extensions: Optional[list[str]] = Field(
        None, description="Filter by file extensions (e.g., ['.nd2', '.czi'])"
    )


class DirectoryListingResponse(BaseModel):
    """Response model for directory listing."""

    success: bool
    directory_path: str
    items: list[FileItem] = []
    error: str | None = None


class SearchFilesRequest(BaseModel):
    """Request model for searching files."""

    search_path: str = Field(..., description="Root directory to search from")
    pattern: Optional[str] = Field(None, description="Search pattern (glob pattern)")
    extensions: Optional[list[str]] = Field(
        None, description="File extensions to search for"
    )
    max_depth: int = Field(10, description="Maximum search depth")
    include_hidden: bool = Field(
        False, description="Include hidden files and directories"
    )


class SearchFilesResponse(BaseModel):
    """Response model for file search."""

    success: bool
    search_path: str
    files: list[FileItem] = []
    total_found: int = 0
    error: str | None = None


class FileInfoRequest(BaseModel):
    """Request model for getting file information."""

    file_path: str = Field(..., description="Path to file")


class FileInfoResponse(BaseModel):
    """Response model for file information."""

    success: bool
    file_info: Optional[FileItem] = None
    is_microscopy_file: bool = False
    metadata_preview: Optional[MicroscopyMetadataResponse] = None
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


@router.get("/features", response_model=FeaturesResponse)
async def get_features() -> FeaturesResponse:
    """Get list of available features for phase contrast and fluorescence channels.

    Returns:
        Response with lists of phase and fluorescence features
    """
    try:
        logger.info("Retrieving available features")

        phase_features = list_phase_features()
        fluorescence_features = list_fluorescence_features()

        logger.info(
            "Found %d phase features and %d fluorescence features",
            len(phase_features),
            len(fluorescence_features),
        )

        return FeaturesResponse(
            phase_features=phase_features,
            fluorescence_features=fluorescence_features,
        )

    except Exception:
        logger.exception("Failed to retrieve features")
        # Return empty lists on error rather than failing completely
        return FeaturesResponse(
            phase_features=[],
            fluorescence_features=[],
        )


# =============================================================================
# WORKFLOW ENDPOINTS
# =============================================================================


@router.post("/workflow/start", response_model=StartWorkflowResponse)
async def start_workflow(request: StartWorkflowRequest) -> StartWorkflowResponse:
    """Start a processing workflow.

    Args:
        request: Workflow start request with configuration

    Returns:
        Response with job ID or error message
    """
    from pyama_backend.main import job_manager
    from pyama_backend.jobs.types import JobStatus

    try:
        # Validate input file exists
        microscopy_path = Path(request.microscopy_path)
        if not microscopy_path.exists():
            logger.error("Microscopy file not found: %s", microscopy_path)
            return StartWorkflowResponse(
                success=False,
                error=f"File not found: {microscopy_path}",
            )

        # Create output directory if it doesn't exist
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create job
        job_id = job_manager.create_job()
        job_manager.update_status(job_id, JobStatus.PENDING, "Workflow queued")

        # Start workflow in background thread
        import threading

        def run_workflow():
            """Run workflow in background thread."""
            try:
                job_manager.update_status(job_id, JobStatus.RUNNING, "Workflow started")

                # Convert request to Channels configuration
                channels = Channels()
                if request.channels.phase:
                    channels.phase = ChannelSelection(
                        channel=request.channels.phase.channel,
                        features=request.channels.phase.features,
                    )
                for fl_channel in request.channels.fluorescence:
                    channels.fluorescence.append(
                        ChannelSelection(
                            channel=fl_channel.channel,
                            features=fl_channel.features,
                        )
                    )

                # Run workflow
                from pyama_core.processing.workflow import (
                    run_workflow as run_core_workflow,
                )

                run_core_workflow(
                    microscopy_path=microscopy_path,
                    output_dir=output_dir,
                    channels=channels,
                    fov_start=request.parameters.fov_start,
                    fov_end=request.parameters.fov_end,
                    batch_size=request.parameters.batch_size,
                    n_workers=request.parameters.n_workers,
                )

                # Set result
                result = {
                    "output_dir": str(output_dir),
                    "results_file": str(output_dir / "processing_results.yaml"),
                }
                job_manager.set_result(job_id, result)

            except Exception as e:
                logger.exception("Workflow failed for job %s", job_id)
                job_manager.update_status(
                    job_id,
                    JobStatus.FAILED,
                    f"Workflow failed: {str(e)}",
                    error=str(e),
                )

        thread = threading.Thread(target=run_workflow, daemon=True)
        thread.start()

        logger.info("Started workflow job: %s", job_id)

        return StartWorkflowResponse(
            success=True,
            job_id=job_id,
            message="Workflow started successfully",
        )

    except Exception as e:
        logger.exception("Failed to start workflow")
        return StartWorkflowResponse(
            success=False,
            error=f"Failed to start workflow: {str(e)}",
        )


@router.get("/workflow/status/{job_id}", response_model=JobStatusResponse)
async def get_workflow_status(job_id: str) -> JobStatusResponse:
    """Get workflow status.

    Args:
        job_id: Job ID

    Returns:
        Response with job status and progress
    """
    from pyama_backend.main import job_manager

    job = job_manager.get_job(job_id)

    if not job:
        logger.warning("Job not found: %s", job_id)
        return JobStatusResponse(
            job_id=job_id,
            status="not_found",
            message="Job not found",
        )

    progress = None
    if job.progress.total > 0:
        progress = {
            "current": job.progress.current,
            "total": job.progress.total,
            "percentage": job.progress.percentage,
        }

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=progress,
        message=job.message,
    )


@router.post("/workflow/cancel/{job_id}", response_model=CancelWorkflowResponse)
async def cancel_workflow(job_id: str) -> CancelWorkflowResponse:
    """Cancel a running workflow.

    Args:
        job_id: Job ID

    Returns:
        Response indicating success or failure
    """
    from pyama_backend.main import job_manager

    success = job_manager.cancel_job(job_id)

    if success:
        return CancelWorkflowResponse(
            success=True,
            message="Workflow cancelled successfully",
        )
    else:
        return CancelWorkflowResponse(
            success=False,
            message="Failed to cancel workflow (job not found or cannot be cancelled)",
        )


@router.get("/workflow/results/{job_id}", response_model=WorkflowResultsResponse)
async def get_workflow_results(job_id: str) -> WorkflowResultsResponse:
    """Get workflow results.

    Args:
        job_id: Job ID

    Returns:
        Response with workflow results or error
    """
    from pyama_backend.main import job_manager
    from pyama_backend.jobs.types import JobStatus

    job = job_manager.get_job(job_id)

    if not job:
        logger.warning("Job not found: %s", job_id)
        return WorkflowResultsResponse(
            success=False,
            error="Job not found",
        )

    if job.status != JobStatus.COMPLETED:
        return WorkflowResultsResponse(
            success=False,
            error=f"Job not completed (status: {job.status.value})",
        )

    if not job.result:
        return WorkflowResultsResponse(
            success=False,
            error="No results available",
        )

    # Extract traces from output directory
    output_dir = Path(job.result["output_dir"])
    traces = []
    if output_dir.exists():
        for trace_file in output_dir.glob("**/*_traces.csv"):
            traces.append(str(trace_file))

    return WorkflowResultsResponse(
        success=True,
        output_dir=job.result.get("output_dir"),
        results_file=job.result.get("results_file"),
        traces=traces,
    )


@router.post("/merge", response_model=MergeResponse)
async def merge_results(request: MergeRequest) -> MergeResponse:
    """Merge processing results with sample definitions.

    Args:
        request: Merge request with file paths

    Returns:
        Response with merge results or error
    """
    try:
        from pyama_core.processing.merge import run_merge

        # Validate input files exist
        sample_yaml = Path(request.sample_yaml)
        processing_results_yaml = Path(request.processing_results_yaml)

        if not sample_yaml.exists():
            logger.error("Sample YAML not found: %s", sample_yaml)
            return MergeResponse(
                success=False,
                error=f"Sample YAML not found: {sample_yaml}",
            )

        if not processing_results_yaml.exists():
            logger.error(
                "Processing results YAML not found: %s", processing_results_yaml
            )
            return MergeResponse(
                success=False,
                error=f"Processing results YAML not found: {processing_results_yaml}",
            )

        # Create output directory
        output_dir = Path(request.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Run merge
        logger.info(
            "Starting merge: %s + %s -> %s",
            sample_yaml,
            processing_results_yaml,
            output_dir,
        )
        result_message = run_merge(sample_yaml, processing_results_yaml, output_dir)

        # Get list of created files
        merged_files = []
        if output_dir.exists():
            for csv_file in output_dir.glob("*.csv"):
                merged_files.append(str(csv_file))

        logger.info("Merge completed: %d files created", len(merged_files))

        return MergeResponse(
            success=True,
            message=result_message,
            output_dir=str(output_dir),
            merged_files=merged_files,
        )

    except Exception as e:
        logger.exception("Failed to merge results")
        return MergeResponse(
            success=False,
            error=f"Failed to merge results: {str(e)}",
        )


# =============================================================================
# FILE EXPLORER ENDPOINTS
# =============================================================================


@router.post("/list-directory", response_model=DirectoryListingResponse)
async def list_directory(request: DirectoryListingRequest) -> DirectoryListingResponse:
    """List contents of a directory with optional filtering.

    Args:
        request: Request containing directory path and filtering options

    Returns:
        Response with directory contents or error message
    """
    directory_path = Path(request.directory_path)

    # Validate directory exists
    if not directory_path.exists():
        logger.error("Directory not found: %s", directory_path)
        return DirectoryListingResponse(
            success=False,
            directory_path=str(directory_path),
            error=f"Directory not found: {directory_path}",
        )

    if not directory_path.is_dir():
        logger.error("Path is not a directory: %s", directory_path)
        return DirectoryListingResponse(
            success=False,
            directory_path=str(directory_path),
            error=f"Path is not a directory: {directory_path}",
        )

    # Special handling for WSL mount points
    if str(directory_path).startswith("/mnt/") and str(directory_path) == "/mnt/c":
        logger.info("Accessing WSL mount point: %s", directory_path)

    try:
        items = []

        # Get directory contents with error handling for individual files
        try:
            directory_items = list(directory_path.iterdir())
        except PermissionError:
            logger.warning(
                "Permission denied accessing some items in directory: %s",
                directory_path,
            )
            # Try to get what we can access
            directory_items = []
            try:
                # Try to access the directory with a different approach
                import os

                directory_items = [
                    Path(directory_path) / name for name in os.listdir(directory_path)
                ]
            except PermissionError:
                logger.error(
                    "Permission denied accessing directory: %s", directory_path
                )
                return DirectoryListingResponse(
                    success=False,
                    directory_path=str(directory_path),
                    error=f"Permission denied accessing directory: {directory_path}",
                )

        for item_path in directory_items:
            try:
                # Skip hidden files if not requested
                if not request.include_hidden and item_path.name.startswith("."):
                    continue

                # Check if it's a file or directory
                is_file = item_path.is_file()
                is_directory = item_path.is_dir()

                # Skip if not file or directory (e.g., symlinks, etc.)
                if not (is_file or is_directory):
                    continue
            except (PermissionError, OSError) as e:
                # Skip files we can't access
                logger.debug("Skipping inaccessible item %s: %s", item_path, e)
                continue

            # Apply extension filter for files
            if is_file and request.filter_extensions:
                if item_path.suffix.lower() not in [
                    ext.lower() for ext in request.filter_extensions
                ]:
                    continue

            # Get file size for files
            size_bytes = None
            if is_file:
                try:
                    size_bytes = item_path.stat().st_size
                except (OSError, PermissionError):
                    size_bytes = None

            # Get modification time
            modified_time = None
            try:
                modified_time = item_path.stat().st_mtime
                modified_time = str(
                    modified_time
                )  # Convert to string for JSON serialization
            except (OSError, PermissionError):
                modified_time = None

            # Get file extension
            extension = item_path.suffix if is_file else None

            items.append(
                FileItem(
                    name=item_path.name,
                    path=str(item_path),
                    is_directory=is_directory,
                    is_file=is_file,
                    size_bytes=size_bytes,
                    modified_time=modified_time,
                    extension=extension,
                )
            )

        # Sort items: directories first, then files, both alphabetically
        items.sort(key=lambda x: (not x.is_directory, x.name.lower()))

        logger.info("Listed directory %s: %d items", directory_path, len(items))

        return DirectoryListingResponse(
            success=True,
            directory_path=str(directory_path),
            items=items,
        )

    except PermissionError:
        logger.error("Permission denied accessing directory: %s", directory_path)
        # Provide helpful error message for WSL mount points
        if str(directory_path).startswith("/mnt/"):
            error_msg = f"Permission denied accessing directory: {directory_path}. This may be due to WSL mount permissions. Try accessing a subdirectory like {directory_path}/Users/YourUsername"
        else:
            error_msg = f"Permission denied accessing directory: {directory_path}"

        return DirectoryListingResponse(
            success=False,
            directory_path=str(directory_path),
            error=error_msg,
        )
    except Exception as e:
        logger.exception("Failed to list directory: %s", directory_path)
        return DirectoryListingResponse(
            success=False,
            directory_path=str(directory_path),
            error=f"Failed to list directory: {str(e)}",
        )


@router.post("/search-files", response_model=SearchFilesResponse)
async def search_files(request: SearchFilesRequest) -> SearchFilesResponse:
    """Search for files recursively with optional pattern matching.

    Args:
        request: Request containing search parameters

    Returns:
        Response with found files or error message
    """
    search_path = Path(request.search_path)

    # Validate search path exists
    if not search_path.exists():
        logger.error("Search path not found: %s", search_path)
        return SearchFilesResponse(
            success=False,
            search_path=str(search_path),
            error=f"Search path not found: {search_path}",
        )

    if not search_path.is_dir():
        logger.error("Search path is not a directory: %s", search_path)
        return SearchFilesResponse(
            success=False,
            search_path=str(search_path),
            error=f"Search path is not a directory: {search_path}",
        )

    try:
        files = []

        # Build glob pattern
        if request.pattern:
            pattern = request.pattern
        else:
            # Default pattern for microscopy files
            if request.extensions:
                ext_pattern = "{" + ",".join(request.extensions) + "}"
                pattern = f"**/*{ext_pattern}"
            else:
                pattern = "**/*.{nd2,czi}"

        # Search for files
        for file_path in search_path.glob(pattern):
            # Skip if not a file
            if not file_path.is_file():
                continue

            # Skip hidden files if not requested
            if not request.include_hidden and file_path.name.startswith("."):
                continue

            # Check depth limit
            try:
                depth = len(file_path.relative_to(search_path).parts) - 1
                if depth > request.max_depth:
                    continue
            except ValueError:
                # File is not relative to search path, skip
                continue

            # Get file size
            size_bytes = None
            try:
                size_bytes = file_path.stat().st_size
            except OSError:
                size_bytes = None

            # Get modification time
            modified_time = None
            try:
                modified_time = file_path.stat().st_mtime
                modified_time = str(modified_time)
            except OSError:
                modified_time = None

            files.append(
                FileItem(
                    name=file_path.name,
                    path=str(file_path),
                    is_directory=False,
                    is_file=True,
                    size_bytes=size_bytes,
                    modified_time=modified_time,
                    extension=file_path.suffix,
                )
            )

        # Sort files by name
        files.sort(key=lambda x: x.name.lower())

        logger.info("Search completed in %s: %d files found", search_path, len(files))

        return SearchFilesResponse(
            success=True,
            search_path=str(search_path),
            files=files,
            total_found=len(files),
        )

    except PermissionError:
        logger.error("Permission denied searching directory: %s", search_path)
        return SearchFilesResponse(
            success=False,
            search_path=str(search_path),
            error=f"Permission denied searching directory: {search_path}",
        )
    except Exception as e:
        logger.exception("Failed to search files: %s", search_path)
        return SearchFilesResponse(
            success=False,
            search_path=str(search_path),
            error=f"Failed to search files: {str(e)}",
        )


@router.post("/file-info", response_model=FileInfoResponse)
async def get_file_info(request: FileInfoRequest) -> FileInfoResponse:
    """Get detailed information about a file, including metadata preview for microscopy files.

    Args:
        request: Request containing file path

    Returns:
        Response with file information and optional metadata preview
    """
    file_path = Path(request.file_path)

    # Validate file exists
    if not file_path.exists():
        logger.error("File not found: %s", file_path)
        return FileInfoResponse(
            success=False,
            error=f"File not found: {file_path}",
        )

    if not file_path.is_file():
        logger.error("Path is not a file: %s", file_path)
        return FileInfoResponse(
            success=False,
            error=f"Path is not a file: {file_path}",
        )

    try:
        # Get basic file information
        stat = file_path.stat()

        file_info = FileItem(
            name=file_path.name,
            path=str(file_path),
            is_directory=False,
            is_file=True,
            size_bytes=stat.st_size,
            modified_time=str(stat.st_mtime),
            extension=file_path.suffix,
        )

        # Check if it's a microscopy file
        is_microscopy_file = file_path.suffix.lower() in [".nd2", ".czi"]

        # Load metadata preview for microscopy files
        metadata_preview = None
        if is_microscopy_file:
            try:
                logger.info("Loading metadata preview for: %s", file_path)
                _, metadata = load_microscopy_file(file_path)
                metadata_preview = MicroscopyMetadataResponse.from_metadata(metadata)
                logger.info("Successfully loaded metadata preview for: %s", file_path)
            except Exception as e:
                logger.warning(
                    "Failed to load metadata preview for %s: %s", file_path, e
                )
                # Don't fail the entire request if metadata loading fails
                metadata_preview = None

        logger.info("Retrieved file info for: %s", file_path)

        return FileInfoResponse(
            success=True,
            file_info=file_info,
            is_microscopy_file=is_microscopy_file,
            metadata_preview=metadata_preview,
        )

    except PermissionError:
        logger.error("Permission denied accessing file: %s", file_path)
        return FileInfoResponse(
            success=False,
            error=f"Permission denied accessing file: {file_path}",
        )
    except Exception as e:
        logger.exception("Failed to get file info: %s", file_path)
        return FileInfoResponse(
            success=False,
            error=f"Failed to get file info: {str(e)}",
        )


@router.get("/recent-files")
async def get_recent_files(
    limit: int = Query(10, description="Maximum number of recent files to return"),
    extensions: Optional[str] = Query(
        None, description="Comma-separated list of extensions to filter by"
    ),
) -> dict:
    """Get recently accessed microscopy files.

    This is a simplified implementation that returns an empty list.
    In a production system, you might want to track file access history.

    Args:
        limit: Maximum number of files to return
        extensions: Optional comma-separated list of extensions to filter by

    Returns:
        Response with recent files list
    """
    # For now, return empty list
    # In a real implementation, you might track file access in a database
    # or use system file access logs

    logger.info("Requested recent files (limit=%d, extensions=%s)", limit, extensions)

    return {
        "success": True,
        "recent_files": [],
        "message": "Recent files tracking not implemented yet",
    }

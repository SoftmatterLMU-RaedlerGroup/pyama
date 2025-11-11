"""Analysis API endpoints."""

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from pyama_backend.jobs.types import JobStatus

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# MODELS ENDPOINT
# =============================================================================


class ModelParameter(BaseModel):
    """Model parameter definition."""

    name: str
    default: float
    bounds: list[float]


class ModelInfo(BaseModel):
    """Model information."""

    name: str
    description: str
    parameters: list[ModelParameter]


class ModelsResponse(BaseModel):
    """Response model for available models."""

    models: list[ModelInfo]


@router.get("/models", response_model=ModelsResponse)
async def get_models() -> ModelsResponse:
    """Get list of available fitting models.

    Returns:
        Response with list of available models and their parameters
    """
    from pyama_core.analysis.models import list_models, get_model, get_types

    try:
        model_names = list_models()
        models_info = []

        for model_name in model_names:
            model = get_model(model_name)
            get_types(model_name)  # Ensure types are available

            # Extract parameters from Params dataclass
            parameters = []
            if hasattr(model, "DEFAULTS") and hasattr(model, "BOUNDS"):
                for (
                    field_name,
                    field_value,
                ) in model.DEFAULTS.__dataclass_fields__.items():
                    default_value = getattr(model.DEFAULTS, field_name)
                    bounds_obj = getattr(model.BOUNDS, field_name, None)

                    # Get bounds tuple
                    if bounds_obj:
                        if isinstance(bounds_obj, tuple) and len(bounds_obj) == 2:
                            bounds = list(bounds_obj)
                        else:
                            bounds = [0.0, 1.0]
                    else:
                        bounds = [0.0, 1.0]

                    parameters.append(
                        ModelParameter(
                            name=field_name,
                            default=default_value,
                            bounds=bounds,
                        )
                    )

            # Get description from docstring
            description = (
                model.__doc__ or f"{model_name} model"
                if hasattr(model, "__doc__")
                else f"{model_name} model"
            )

            models_info.append(
                ModelInfo(
                    name=model_name,
                    description=description.strip()
                    if description
                    else f"{model_name} model",
                    parameters=parameters,
                )
            )

        logger.info("Retrieved %d model(s)", len(models_info))

        return ModelsResponse(models=models_info)

    except Exception:
        logger.exception("Failed to retrieve models")
        return ModelsResponse(models=[])


# =============================================================================
# FIT ANALYSIS ENDPOINTS
# =============================================================================


class LoadTracesRequest(BaseModel):
    """Request model for loading trace data."""

    csv_path: str = Field(..., description="Path to CSV file containing trace data")


class TraceDataInfo(BaseModel):
    """Trace data information."""

    n_cells: int
    n_timepoints: int
    time_units: str
    columns: list[str]


class LoadTracesResponse(BaseModel):
    """Response model for loading traces."""

    success: bool
    data: Optional[TraceDataInfo] = None
    error: Optional[str] = None


@router.post("/load-traces", response_model=LoadTracesResponse)
async def load_traces(request: LoadTracesRequest) -> LoadTracesResponse:
    """Load trace data from a CSV file.

    Args:
        request: Request containing CSV file path

    Returns:
        Response with trace data information or error
    """
    import pandas as pd

    csv_path = Path(request.csv_path)

    # Validate file exists
    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return LoadTracesResponse(
            success=False,
            error=f"File not found: {csv_path}",
        )

    try:
        # Load CSV
        df = pd.read_csv(csv_path)

        # Extract information
        data_info = TraceDataInfo(
            n_cells=len(df.columns),
            n_timepoints=len(df),
            time_units="hours",  # Default assumption
            columns=list(df.columns),
        )

        logger.info(
            "Loaded trace data: %d cells, %d timepoints",
            data_info.n_cells,
            data_info.n_timepoints,
        )

        return LoadTracesResponse(
            success=True,
            data=data_info,
        )

    except Exception as e:
        logger.exception("Failed to load trace data: %s", csv_path)
        return LoadTracesResponse(
            success=False,
            error=f"Failed to load CSV: {str(e)}",
        )


class StartFittingRequest(BaseModel):
    """Request model for starting fitting analysis."""

    csv_path: str = Field(..., description="Path to CSV file with trace data")
    model_type: str = Field(..., description="Model type to use")
    model_params: Optional[dict[str, float]] = Field(
        None, description="Optional initial parameters"
    )
    model_bounds: Optional[dict[str, list[float]]] = Field(
        None, description="Optional parameter bounds"
    )


class StartFittingResponse(BaseModel):
    """Response model for starting fitting."""

    success: bool
    job_id: Optional[str] = None
    message: str = ""
    error: Optional[str] = None


class FittingStatusResponse(BaseModel):
    """Response model for fitting status."""

    job_id: str
    status: str
    progress: Optional[dict] = None
    message: str


class CancelFittingResponse(BaseModel):
    """Response model for cancelling fitting."""

    success: bool
    message: str


class FittingResultsResponse(BaseModel):
    """Response model for fitting results."""

    success: bool
    results_file: Optional[str] = None
    summary: Optional[dict] = None
    error: Optional[str] = None


@router.post("/fitting/start", response_model=StartFittingResponse)
async def start_fitting(request: StartFittingRequest) -> StartFittingResponse:
    """Start fitting analysis on trace data.

    Args:
        request: Fitting start request with configuration

    Returns:
        Response with job ID or error message
    """
    from pyama_backend.main import job_manager

    try:
        # Validate CSV file exists
        csv_path = Path(request.csv_path)
        if not csv_path.exists():
            logger.error("CSV file not found: %s", csv_path)
            return StartFittingResponse(
                success=False,
                error=f"File not found: {csv_path}",
            )

        # Create job
        job_id = job_manager.create_job()
        job_manager.update_status(job_id, JobStatus.PENDING, "Fitting analysis queued")

        # Start fitting in background thread
        import threading

        def run_fitting():
            """Run fitting analysis in background thread."""
            try:
                job_manager.update_status(
                    job_id, JobStatus.RUNNING, "Fitting analysis started"
                )

                import numpy as np
                import pandas as pd
                from pyama_core.analysis.fitting import fit_model
                from pyama_core.analysis.models import get_model
                from pyama_core.types.analysis import FitParam, FitParams

                # Load CSV
                df = pd.read_csv(csv_path)

                # Get model object
                model = get_model(request.model_type.lower())

                # Prepare fixed and fit parameters
                fixed_params = model.DEFAULT_FIXED
                
                # Start with default fit parameters
                fit_params: FitParams = {}
                for param_name, param in model.DEFAULT_FIT.items():
                    # Use user-provided value if available, otherwise use default
                    value = request.model_params.get(param_name, param.value) if request.model_params else param.value
                    
                    # Use user-provided bounds if available, otherwise use default
                    if request.model_bounds and param_name in request.model_bounds:
                        bounds = request.model_bounds[param_name]
                        if isinstance(bounds, list):
                            lb, ub = float(bounds[0]), float(bounds[1])
                        else:
                            lb, ub = float(bounds[0]), float(bounds[1])
                    else:
                        lb, ub = param.lb, param.ub
                    
                    fit_params[param_name] = FitParam(
                        name=param.name,
                        value=value,
                        lb=lb,
                        ub=ub,
                    )

                # Fit each cell
                results = []
                total_cells = len(df.columns)

                for idx, cell_id in enumerate(df.columns):
                    # Check if cancelled
                    if (
                        job_manager.get_job(job_id)
                        and job_manager.get_job(job_id).cancelled
                    ):
                        job_manager.update_status(
                            job_id, JobStatus.CANCELLED, "Fitting cancelled"
                        )
                        return

                    # Get trace data directly from DataFrame
                    t_data = df.index.values.astype(np.float64)
                    y_data = df[cell_id].values.astype(np.float64)

                    # Fit model
                    result = fit_model(
                        model,
                        t_data,
                        y_data,
                        fixed_params,
                        fit_params,
                    )

                    # Convert fitted_params to serializable format
                    fitted_params_dict = {
                        param_name: param.value
                        for param_name, param in result.fitted_params.items()
                    }

                    results.append(
                        {
                            "cell_id": cell_id,
                            "model_type": request.model_type,
                            "success": result.success,
                            "r_squared": result.r_squared,
                            "fitted_params": fitted_params_dict,
                        }
                    )

                    # Update progress (0-indexed to match merge pattern)
                    job_manager.update_progress(
                        job_id,
                        idx,
                        total_cells,
                        "Fitting cells",
                    )

                # Save results
                output_path = (
                    csv_path.parent / f"{csv_path.stem}_fitted_{request.model_type}.csv"
                )
                results_df = pd.DataFrame(results)
                results_df.to_csv(output_path, index=False)

                # Calculate summary
                successful_fits = sum(1 for r in results if r["success"])
                failed_fits = total_cells - successful_fits
                mean_r_squared = (
                    sum(r["r_squared"] for r in results) / total_cells
                    if results
                    else 0.0
                )

                summary = {
                    "total_cells": total_cells,
                    "successful_fits": successful_fits,
                    "failed_fits": failed_fits,
                    "mean_r_squared": mean_r_squared,
                }

                # Set result
                result = {
                    "results_file": str(output_path),
                    "summary": summary,
                }
                job_manager.set_result(job_id, result)

            except Exception as e:
                logger.exception("Fitting failed for job %s", job_id)
                job_manager.update_status(
                    job_id,
                    JobStatus.FAILED,
                    f"Fitting failed: {str(e)}",
                    error=str(e),
                )

        thread = threading.Thread(target=run_fitting, daemon=True)
        thread.start()

        logger.info("Started fitting job: %s", job_id)

        return StartFittingResponse(
            success=True,
            job_id=job_id,
            message="Fitting started successfully",
        )

    except Exception as e:
        logger.exception("Failed to start fitting")
        return StartFittingResponse(
            success=False,
            error=f"Failed to start fitting: {str(e)}",
        )


@router.get("/fitting/status/{job_id}", response_model=FittingStatusResponse)
async def get_fitting_status(job_id: str) -> FittingStatusResponse:
    """Get fitting status.

    Args:
        job_id: Job ID

    Returns:
        Response with job status and progress
    """
    from pyama_backend.main import job_manager

    job = job_manager.get_job(job_id)

    if not job:
        logger.warning("Job not found: %s", job_id)
        return FittingStatusResponse(
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

    return FittingStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        progress=progress,
        message=job.message,
    )


@router.post("/fitting/cancel/{job_id}", response_model=CancelFittingResponse)
async def cancel_fitting(job_id: str) -> CancelFittingResponse:
    """Cancel a running fitting job.

    Args:
        job_id: Job ID

    Returns:
        Response indicating success or failure
    """
    from pyama_backend.main import job_manager

    success = job_manager.cancel_job(job_id)

    if success:
        return CancelFittingResponse(
            success=True,
            message="Fitting cancelled successfully",
        )
    else:
        return CancelFittingResponse(
            success=False,
            message="Failed to cancel fitting (job not found or cannot be cancelled)",
        )


@router.get("/fitting/results/{job_id}", response_model=FittingResultsResponse)
async def get_fitting_results(job_id: str) -> FittingResultsResponse:
    """Get fitting results.

    Args:
        job_id: Job ID

    Returns:
        Response with fitting results or error
    """
    from pyama_backend.main import job_manager
    from pyama_backend.jobs.types import JobStatus

    job = job_manager.get_job(job_id)

    if not job:
        logger.warning("Job not found: %s", job_id)
        return FittingResultsResponse(
            success=False,
            error="Job not found",
        )

    if job.status != JobStatus.COMPLETED:
        return FittingResultsResponse(
            success=False,
            error=f"Job not completed (status: {job.status.value})",
        )

    if not job.result:
        return FittingResultsResponse(
            success=False,
            error="No results available",
        )

    return FittingResultsResponse(
        success=True,
        results_file=job.result.get("results_file"),
        summary=job.result.get("summary"),
    )

"""
Fitting service utilities (pure Python, no Qt dependencies).

Centralizes model parameter preparation, progress reporting, and result
flattening/saving for analysis fitting so UI layers only handle Qt plumbing.
"""

import logging
from pathlib import Path
from typing import Callable

import pandas as pd

from pyama_core.analysis.fitting import fit_trace_data
from pyama_core.analysis.models import get_model
from pyama_core.io.analysis_csv import load_analysis_csv
from pyama_core.types.analysis import FitParam, FitParams, FixedParam, FixedParams

logger = logging.getLogger(__name__)


class FittingService:
    """Service for fitting analysis CSV files."""

    def __init__(
        self, progress_reporter: Callable[[dict], None] | None = None
    ) -> None:
        """
        Args:
            progress_reporter: Optional callable receiving a progress event dict.
        """
        self._progress_reporter = progress_reporter

    def fit_csv_file(
        self,
        csv_file: Path,
        model_type: str,
        model_params: dict[str, float] | None = None,
        model_bounds: dict[str, tuple[float, float]] | None = None,
        *,
        progress_reporter: Callable[[dict], None] | None = None,
    ) -> tuple[pd.DataFrame | None, Path | None]:
        """Fit traces in a CSV file and save results.

        Args:
            csv_file: Path to the input analysis CSV file.
            model_type: Model type to fit.
            model_params: Optional manual parameter overrides (fixed and fit).
            model_bounds: Optional manual bounds for fit parameters.
            progress_reporter: Optional callable to receive progress events.

        Returns:
            Tuple of (results DataFrame or None, saved CSV Path or None).
        """
        reporter = progress_reporter or self._progress_reporter

        if not csv_file.exists():
            raise FileNotFoundError(f"CSV file not found: {csv_file}")

        logger.info(
            "Processing %s with model=%s (manual_params=%d, manual_bounds=%d)",
            csv_file.name,
            model_type,
            len(model_params or {}),
            len(model_bounds or {}),
        )

        df = load_analysis_csv(csv_file)
        model = get_model(model_type)

        fixed_params = self._build_fixed_params(model, model_params)
        fit_params = self._build_fit_params(model, model_params, model_bounds)
        progress_callback = self._build_progress_callback(csv_file, reporter)

        results = fit_trace_data(
            df,
            model_type,
            fixed_params=fixed_params,
            fit_params=fit_params,
            progress_callback=progress_callback,
        )

        results_df = self._flatten_results(model_type, results)
        if results_df is None or results_df.empty:
            return results_df, None

        saved_csv_path = csv_file.with_name(
            f"{csv_file.stem}_fitted_{model_type}.csv"
        )
        try:
            results_df.to_csv(saved_csv_path, index=False)
            logger.info(
                "Saved fitted results to %s (%d rows)",
                saved_csv_path,
                len(results_df),
            )
        except Exception as exc:  # pragma: no cover - I/O best effort
            logger.warning("Failed to save fitted results for %s: %s", saved_csv_path, exc)
            saved_csv_path = None

        return results_df, saved_csv_path

    def _build_fixed_params(
        self, model, model_params: dict[str, float] | None
    ) -> FixedParams:
        fixed_params: FixedParams = {}
        for param_name, param in model.DEFAULT_FIXED.items():
            value = model_params.get(param_name, param.value) if model_params else param.value
            fixed_params[param_name] = FixedParam(name=param.name, value=value)
        return fixed_params

    def _build_fit_params(
        self,
        model,
        model_params: dict[str, float] | None,
        model_bounds: dict[str, tuple[float, float]] | None,
    ) -> FitParams:
        fit_params: FitParams = {}
        for param_name, param in model.DEFAULT_FIT.items():
            value = model_params.get(param_name, param.value) if model_params else param.value
            if model_bounds and param_name in model_bounds:
                lb, ub = model_bounds[param_name]
            else:
                lb, ub = param.lb, param.ub
            fit_params[param_name] = FitParam(
                name=param.name,
                value=value,
                lb=lb,
                ub=ub,
            )
        return fit_params

    def _build_progress_callback(
        self, csv_file: Path, reporter: Callable[[dict], None] | None
    ) -> Callable[[int, int, str], None]:
        def progress_callback(current: int, total: int, message: str) -> None:
            """Progress callback that logs throttled progress updates."""
            current_idx = current + 1  # convert 0-based to 1-based for display

            if total > 0:
                should_log = (
                    current_idx == 1 or current_idx % 30 == 0 or current_idx == total
                )
                if not should_log:
                    return
                progress = int((current_idx / total) * 100)
                logger.info(
                    "%s: %d/%d (%d%%) for %s",
                    message,
                    current_idx,
                    total,
                    progress,
                    csv_file.name,
                )
                if reporter:
                    reporter(
                        {
                            "step": "analysis_fitting",
                            "file": csv_file.name,
                            "current": current_idx,
                            "total": total,
                            "progress": progress,
                            "message": message,
                        }
                    )
            else:
                logger.info("%s: %d for %s", message, current_idx, csv_file.name)
                if reporter:
                    reporter(
                        {
                            "step": "analysis_fitting",
                            "file": csv_file.name,
                            "current": current_idx,
                            "total": None,
                            "progress": None,
                            "message": message,
                        }
                    )

        return progress_callback

    def _flatten_results(
        self, model_type: str, results: list[tuple[tuple[int, int], object]]
    ) -> pd.DataFrame | None:
        if not results:
            return None

        flattened_results = []
        for (fov, cell), result in results:
            if not result:
                continue
            row = {
                "fov": fov,
                "cell": cell,
                "model_type": model_type,
                "success": result.success,
                "r_squared": result.r_squared,
            }
            row.update(
                {param_name: param.value for param_name, param in result.fitted_params.items()}
            )
            flattened_results.append(row)

        if not flattened_results:
            return None
        return pd.DataFrame(flattened_results)

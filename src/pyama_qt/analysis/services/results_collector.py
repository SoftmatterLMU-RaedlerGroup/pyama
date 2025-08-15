"""
Results collection and aggregation utilities.

Combines fitting results from multiple FOVs into project-level summaries.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any
import numpy as np
from datetime import datetime

from pyama_qt.core.logging_config import get_logger


class ResultsCollector:
    """Collects and aggregates fitting results from multiple FOVs."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.results_cache = {}

    def collect_all_results(self, data_folder: Path) -> pd.DataFrame:
        """
        Collect all fitting results from FOV subdirectories.

        Args:
            data_folder: Root folder containing FOV subdirectories

        Returns:
            DataFrame with combined results from all FOVs
        """
        all_results = []

        # Find all FOV directories
        fov_dirs = [
            d for d in data_folder.iterdir() if d.is_dir() and d.name.startswith("fov_")
        ]

        self.logger.info(f"Collecting results from {len(fov_dirs)} FOV directories")

        for fov_dir in sorted(fov_dirs):
            try:
                fov_results = self.collect_fov_results(fov_dir)
                if not fov_results.empty:
                    all_results.append(fov_results)

            except Exception as e:
                self.logger.warning(
                    f"Error collecting results from {fov_dir}: {str(e)}"
                )

        if not all_results:
            self.logger.warning("No fitting results found")
            return pd.DataFrame()

        # Combine all results
        combined_df = pd.concat(all_results, ignore_index=True)

        self.logger.info(f"Collected {len(combined_df)} total fitting results")

        return combined_df

    def collect_fov_results(self, fov_dir: Path) -> pd.DataFrame:
        """
        Collect fitting results from a single FOV directory.

        Args:
            fov_dir: Path to FOV directory

        Returns:
            DataFrame with results from this FOV
        """
        # Look for fitted results CSV files
        fitted_files = list(fov_dir.glob("*_fitted.csv"))

        if not fitted_files:
            return pd.DataFrame()

        # Use the first fitted file found
        fitted_file = fitted_files[0]

        try:
            df = pd.read_csv(fitted_file)

            # Ensure FOV column is present and correct
            if "fov" not in df.columns:
                df["fov"] = fov_dir.name

            return df

        except Exception as e:
            self.logger.error(f"Error reading {fitted_file}: {str(e)}")
            return pd.DataFrame()

    def generate_summary_statistics(self, results_df: pd.DataFrame) -> Dict[str, Any]:
        """
        Generate summary statistics from fitting results.

        Args:
            results_df: DataFrame with fitting results

        Returns:
            Dictionary with summary statistics
        """
        if results_df.empty:
            return {}

        summary = {
            "timestamp": datetime.now().isoformat(),
            "total_cells": len(results_df),
            "total_fovs": results_df["fov"].nunique()
            if "fov" in results_df.columns
            else 1,
            "successful_fits": (results_df["success"]).sum()
            if "success" in results_df.columns
            else 0,
            "failed_fits": (not results_df["success"]).sum()
            if "success" in results_df.columns
            else 0,
        }

        if summary["total_cells"] > 0:
            summary["success_rate"] = (
                summary["successful_fits"] / summary["total_cells"]
            )
        else:
            summary["success_rate"] = 0.0

        # Parameter statistics for successful fits
        if summary["successful_fits"] > 0:
            successful_df = results_df[results_df["success"]]

            # Find parameter columns (exclude metadata columns)
            metadata_cols = {
                "fov",
                "cell_id",
                "model_type",
                "success",
                "r_squared",
                "residual_sum_squares",
                "n_function_calls",
                "message",
            }
            param_cols = [
                col for col in successful_df.columns if col not in metadata_cols
            ]

            param_stats = {}
            for param in param_cols:
                if successful_df[param].dtype in [
                    np.float64,
                    np.float32,
                    np.int64,
                    np.int32,
                ]:
                    values = successful_df[param].dropna()
                    if len(values) > 0:
                        param_stats[param] = {
                            "mean": float(values.mean()),
                            "std": float(values.std()),
                            "median": float(values.median()),
                            "min": float(values.min()),
                            "max": float(values.max()),
                            "count": len(values),
                        }

            summary["parameter_statistics"] = param_stats

        # R-squared statistics
        if "r_squared" in results_df.columns:
            r2_values = results_df["r_squared"].dropna()
            if len(r2_values) > 0:
                summary["r_squared_stats"] = {
                    "mean": float(r2_values.mean()),
                    "std": float(r2_values.std()),
                    "median": float(r2_values.median()),
                    "min": float(r2_values.min()),
                    "max": float(r2_values.max()),
                }

        return summary

    def save_combined_results(
        self, results_df: pd.DataFrame, output_path: Path, include_summary: bool = True
    ) -> Dict[str, Path]:
        """
        Save combined results to files.

        Args:
            results_df: DataFrame with fitting results
            output_path: Output directory path
            include_summary: Whether to generate summary statistics

        Returns:
            Dictionary of saved file paths
        """
        output_path.mkdir(parents=True, exist_ok=True)
        saved_files = {}

        # Save combined results CSV
        results_csv = output_path / "combined_fitting_results.csv"
        results_df.to_csv(results_csv, index=False)
        saved_files["results_csv"] = results_csv

        self.logger.info(f"Saved combined results to {results_csv}")

        if include_summary:
            # Generate and save summary
            summary = self.generate_summary_statistics(results_df)

            # Save summary as JSON
            import json

            summary_json = output_path / "analysis_summary.json"
            with open(summary_json, "w") as f:
                json.dump(summary, f, indent=2)
            saved_files["summary_json"] = summary_json

            # Save summary as Excel with multiple sheets
            try:
                summary_excel = output_path / "analysis_summary.xlsx"

                with pd.ExcelWriter(summary_excel, engine="openpyxl") as writer:
                    # Main results sheet
                    results_df.to_excel(writer, sheet_name="Results", index=False)

                    # Summary statistics sheet
                    if "parameter_statistics" in summary:
                        param_stats_df = pd.DataFrame(summary["parameter_statistics"]).T
                        param_stats_df.to_excel(
                            writer, sheet_name="Parameter_Statistics"
                        )

                    # Basic summary sheet
                    basic_summary = {
                        "Metric": [
                            "Total Cells",
                            "Total FOVs",
                            "Successful Fits",
                            "Failed Fits",
                            "Success Rate",
                        ],
                        "Value": [
                            summary["total_cells"],
                            summary["total_fovs"],
                            summary["successful_fits"],
                            summary["failed_fits"],
                            f"{summary['success_rate']:.1%}",
                        ],
                    }
                    basic_df = pd.DataFrame(basic_summary)
                    basic_df.to_excel(writer, sheet_name="Summary", index=False)

                saved_files["summary_excel"] = summary_excel
                self.logger.info(f"Saved summary Excel to {summary_excel}")

            except Exception as e:
                self.logger.warning(f"Could not save Excel summary: {str(e)}")

        return saved_files

    def filter_successful_results(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Filter results to include only successful fits.

        Args:
            results_df: DataFrame with fitting results

        Returns:
            DataFrame with only successful fits
        """
        if "success" not in results_df.columns:
            return results_df

        return results_df[results_df["success"]].copy()

    def group_by_condition(
        self, results_df: pd.DataFrame, condition_column: str = "fov"
    ) -> Dict[str, pd.DataFrame]:
        """
        Group results by experimental condition.

        Args:
            results_df: DataFrame with fitting results
            condition_column: Column to group by

        Returns:
            Dictionary mapping conditions to result DataFrames
        """
        if condition_column not in results_df.columns:
            return {"all": results_df}

        grouped = {}
        for condition, group_df in results_df.groupby(condition_column):
            grouped[str(condition)] = group_df.reset_index(drop=True)

        return grouped

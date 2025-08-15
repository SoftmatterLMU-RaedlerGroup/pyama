"""
Export utilities for analysis results.

Provides functionality to export results in various formats with visualizations.
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
from typing import Dict
import seaborn as sns

from pyama_qt.core.logging_config import get_logger


class ResultsExporter:
    """Handles export of analysis results to various formats."""

    def __init__(self):
        self.logger = get_logger(__name__)
        # Set matplotlib style for publication-quality plots
        plt.style.use("default")
        sns.set_palette("husl")

    def export_full_report(
        self,
        results_df: pd.DataFrame,
        output_dir: Path,
        project_name: str = "analysis_results",
    ) -> Dict[str, Path]:
        """
        Export a complete analysis report.

        Args:
            results_df: DataFrame with fitting results
            output_dir: Output directory
            project_name: Name for output files

        Returns:
            Dictionary of exported file paths
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        exported_files = {}

        self.logger.info(f"Exporting full report to {output_dir}")

        # Export data files
        data_files = self.export_data_files(results_df, output_dir, project_name)
        exported_files.update(data_files)

        # Export visualizations
        plot_files = self.export_visualizations(results_df, output_dir, project_name)
        exported_files.update(plot_files)

        # Export summary report
        summary_files = self.export_summary_report(results_df, output_dir, project_name)
        exported_files.update(summary_files)

        self.logger.info(f"Exported {len(exported_files)} files")
        return exported_files

    def export_data_files(
        self, results_df: pd.DataFrame, output_dir: Path, project_name: str
    ) -> Dict[str, Path]:
        """Export data in various formats."""
        exported = {}

        # CSV export
        csv_path = output_dir / f"{project_name}_results.csv"
        results_df.to_csv(csv_path, index=False)
        exported["results_csv"] = csv_path

        # Excel export with multiple sheets
        try:
            excel_path = output_dir / f"{project_name}_results.xlsx"

            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                # All results
                results_df.to_excel(writer, sheet_name="All_Results", index=False)

                # Successful fits only
                if "success" in results_df.columns:
                    successful_df = results_df[results_df["success"]]
                    successful_df.to_excel(
                        writer, sheet_name="Successful_Fits", index=False
                    )

                # Group by FOV if available
                if "fov" in results_df.columns and results_df["fov"].nunique() > 1:
                    for fov_name, fov_group in results_df.groupby("fov"):
                        sheet_name = f"FOV_{fov_name.replace('fov_', '')}"
                        fov_group.to_excel(writer, sheet_name=sheet_name, index=False)

            exported["results_excel"] = excel_path

        except Exception as e:
            self.logger.warning(f"Could not export Excel file: {str(e)}")

        return exported

    def export_visualizations(
        self, results_df: pd.DataFrame, output_dir: Path, project_name: str
    ) -> Dict[str, Path]:
        """Export visualization plots."""
        exported = {}

        if results_df.empty:
            return exported

        plots_dir = output_dir / "plots"
        plots_dir.mkdir(exist_ok=True)

        # Create comprehensive PDF report
        pdf_path = plots_dir / f"{project_name}_plots.pdf"

        with PdfPages(pdf_path) as pdf:
            # Parameter distributions
            self._plot_parameter_distributions(results_df, pdf)

            # Quality metrics
            self._plot_quality_metrics(results_df, pdf)

            # Parameter correlations
            self._plot_parameter_correlations(results_df, pdf)

            # FOV comparisons if available
            if "fov" in results_df.columns and results_df["fov"].nunique() > 1:
                self._plot_fov_comparisons(results_df, pdf)

        exported["plots_pdf"] = pdf_path

        # Export individual PNG plots
        png_files = self._export_individual_plots(results_df, plots_dir, project_name)
        exported.update(png_files)

        return exported

    def _plot_parameter_distributions(self, results_df: pd.DataFrame, pdf: PdfPages):
        """Plot parameter distribution histograms."""
        if "success" not in results_df.columns:
            return

        successful_df = results_df[results_df["success"]]
        if successful_df.empty:
            return

        # Find parameter columns
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
            col
            for col in successful_df.columns
            if col not in metadata_cols
            and successful_df[col].dtype in [np.float64, np.float32]
        ]

        if not param_cols:
            return

        # Create subplots
        n_params = len(param_cols)
        n_cols = min(3, n_params)
        n_rows = (n_params + n_cols - 1) // n_cols

        fig, axes = plt.subplots(n_rows, n_cols, figsize=(12, 4 * n_rows))
        if n_params == 1:
            axes = [axes]
        elif n_rows == 1:
            axes = axes.flatten()
        else:
            axes = axes.flatten()

        for i, param in enumerate(param_cols):
            ax = axes[i]
            values = successful_df[param].dropna()

            if len(values) > 0:
                ax.hist(values, bins=20, alpha=0.7, color="skyblue", edgecolor="black")
                ax.set_xlabel(param.replace("_", " ").title())
                ax.set_ylabel("Frequency")
                ax.set_title(f"Distribution of {param.replace('_', ' ').title()}")
                ax.grid(True, alpha=0.3)

                # Add statistics text
                mean_val = values.mean()
                std_val = values.std()
                ax.text(
                    0.02,
                    0.98,
                    f"μ = {mean_val:.3f}\\nσ = {std_val:.3f}",
                    transform=ax.transAxes,
                    verticalalignment="top",
                    bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
                )

        # Hide unused subplots
        for i in range(n_params, len(axes)):
            axes[i].set_visible(False)

        plt.tight_layout()
        plt.suptitle("Parameter Distributions", y=1.02)
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _plot_quality_metrics(self, results_df: pd.DataFrame, pdf: PdfPages):
        """Plot quality metrics."""
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # Success rate plot
        if "success" in results_df.columns:
            success_counts = results_df["success"].value_counts()
            colors = ["lightcoral", "lightgreen"]
            axes[0].pie(
                success_counts.values,
                labels=["Failed", "Successful"],
                autopct="%1.1f%%",
                colors=colors,
            )
            axes[0].set_title("Fitting Success Rate")

        # R-squared distribution
        if "r_squared" in results_df.columns:
            r2_values = results_df["r_squared"].dropna()
            if len(r2_values) > 0:
                axes[1].hist(
                    r2_values, bins=20, alpha=0.7, color="lightblue", edgecolor="black"
                )
                axes[1].set_xlabel("R²")
                axes[1].set_ylabel("Frequency")
                axes[1].set_title("R² Distribution")
                axes[1].grid(True, alpha=0.3)

                # Add mean line
                mean_r2 = r2_values.mean()
                axes[1].axvline(
                    mean_r2, color="red", linestyle="--", label=f"Mean = {mean_r2:.3f}"
                )
                axes[1].legend()

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _plot_parameter_correlations(self, results_df: pd.DataFrame, pdf: PdfPages):
        """Plot parameter correlation matrix."""
        if "success" not in results_df.columns:
            return

        successful_df = results_df[results_df["success"]]
        if successful_df.empty:
            return

        # Find numeric parameter columns
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
        numeric_cols = [
            col
            for col in successful_df.columns
            if col not in metadata_cols
            and successful_df[col].dtype in [np.float64, np.float32]
        ]

        if len(numeric_cols) < 2:
            return

        # Calculate correlation matrix
        corr_data = successful_df[numeric_cols]
        correlation_matrix = corr_data.corr()

        # Create heatmap
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(
            correlation_matrix,
            annot=True,
            cmap="coolwarm",
            center=0,
            square=True,
            ax=ax,
            cbar_kws={"shrink": 0.8},
        )
        ax.set_title("Parameter Correlation Matrix")

        # Improve label formatting
        ax.set_xticklabels(
            [col.replace("_", " ").title() for col in numeric_cols],
            rotation=45,
            ha="right",
        )
        ax.set_yticklabels(
            [col.replace("_", " ").title() for col in numeric_cols], rotation=0
        )

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _plot_fov_comparisons(self, results_df: pd.DataFrame, pdf: PdfPages):
        """Plot comparisons between FOVs."""
        if "fov" not in results_df.columns or "success" not in results_df.columns:
            return

        successful_df = results_df[results_df["success"]]
        if successful_df.empty:
            return

        # Success rates by FOV
        fig, axes = plt.subplots(2, 1, figsize=(12, 10))

        # Success rate by FOV
        fov_success = results_df.groupby("fov")["success"].agg(["count", "sum"])
        fov_success["rate"] = fov_success["sum"] / fov_success["count"]

        fov_names = fov_success.index
        axes[0].bar(
            range(len(fov_names)), fov_success["rate"], alpha=0.7, color="lightgreen"
        )
        axes[0].set_xlabel("FOV")
        axes[0].set_ylabel("Success Rate")
        axes[0].set_title("Fitting Success Rate by FOV")
        axes[0].set_xticks(range(len(fov_names)))
        axes[0].set_xticklabels(fov_names, rotation=45)
        axes[0].grid(True, alpha=0.3)

        # R² by FOV if available
        if "r_squared" in successful_df.columns:
            fov_r2 = successful_df.groupby("fov")["r_squared"].mean()
            axes[1].bar(
                range(len(fov_r2.index)), fov_r2.values, alpha=0.7, color="lightblue"
            )
            axes[1].set_xlabel("FOV")
            axes[1].set_ylabel("Mean R²")
            axes[1].set_title("Mean R² by FOV")
            axes[1].set_xticks(range(len(fov_r2.index)))
            axes[1].set_xticklabels(fov_r2.index, rotation=45)
            axes[1].grid(True, alpha=0.3)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches="tight")
        plt.close()

    def _export_individual_plots(
        self, results_df: pd.DataFrame, plots_dir: Path, project_name: str
    ) -> Dict[str, Path]:
        """Export individual PNG plots."""
        exported = {}

        try:
            # Parameter distributions as individual PNGs
            if "success" in results_df.columns:
                successful_df = results_df[results_df["success"]]
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
                    col
                    for col in successful_df.columns
                    if col not in metadata_cols
                    and successful_df[col].dtype in [np.float64, np.float32]
                ]

                for param in param_cols[:6]:  # Limit to first 6 parameters
                    values = successful_df[param].dropna()
                    if len(values) > 0:
                        fig, ax = plt.subplots(figsize=(8, 6))
                        ax.hist(
                            values,
                            bins=20,
                            alpha=0.7,
                            color="skyblue",
                            edgecolor="black",
                        )
                        ax.set_xlabel(param.replace("_", " ").title())
                        ax.set_ylabel("Frequency")
                        ax.set_title(
                            f"Distribution of {param.replace('_', ' ').title()}"
                        )
                        ax.grid(True, alpha=0.3)

                        png_path = (
                            plots_dir / f"{project_name}_{param}_distribution.png"
                        )
                        plt.savefig(png_path, dpi=300, bbox_inches="tight")
                        exported[f"{param}_dist_png"] = png_path
                        plt.close()

        except Exception as e:
            self.logger.warning(f"Error exporting individual plots: {str(e)}")

        return exported

    def export_summary_report(
        self, results_df: pd.DataFrame, output_dir: Path, project_name: str
    ) -> Dict[str, Path]:
        """Export a text summary report."""
        exported = {}

        report_path = output_dir / f"{project_name}_summary_report.txt"

        try:
            with open(report_path, "w") as f:
                f.write("PyAMA-Qt Analysis Summary Report\\n")
                f.write(f"Generated: {pd.Timestamp.now()}\\n")
                f.write("=" * 50 + "\\n\\n")

                # Basic statistics
                f.write("BASIC STATISTICS\\n")
                f.write("-" * 20 + "\\n")
                f.write(f"Total cells analyzed: {len(results_df)}\\n")

                if "fov" in results_df.columns:
                    f.write(f"Total FOVs: {results_df['fov'].nunique()}\\n")

                if "success" in results_df.columns:
                    n_success = (results_df["success"]).sum()
                    n_failed = (not results_df["success"]).sum()
                    success_rate = n_success / len(results_df) * 100

                    f.write(f"Successful fits: {n_success}\\n")
                    f.write(f"Failed fits: {n_failed}\\n")
                    f.write(f"Success rate: {success_rate:.1f}%\\n")

                f.write("\\n")

                # Parameter statistics
                if "success" in results_df.columns:
                    successful_df = results_df[results_df["success"]]
                    if not successful_df.empty:
                        f.write("PARAMETER STATISTICS (Successful Fits)\\n")
                        f.write("-" * 40 + "\\n")

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
                            col
                            for col in successful_df.columns
                            if col not in metadata_cols
                            and successful_df[col].dtype in [np.float64, np.float32]
                        ]

                        for param in param_cols:
                            values = successful_df[param].dropna()
                            if len(values) > 0:
                                f.write(f"{param.replace('_', ' ').title()}:\\n")
                                f.write(f"  Mean: {values.mean():.6f}\\n")
                                f.write(f"  Std:  {values.std():.6f}\\n")
                                f.write(f"  Min:  {values.min():.6f}\\n")
                                f.write(f"  Max:  {values.max():.6f}\\n")
                                f.write("\\n")

                # Quality metrics
                if "r_squared" in results_df.columns:
                    r2_values = results_df["r_squared"].dropna()
                    if len(r2_values) > 0:
                        f.write("QUALITY METRICS\\n")
                        f.write("-" * 15 + "\\n")
                        f.write(f"R² Mean: {r2_values.mean():.4f}\\n")
                        f.write(f"R² Std:  {r2_values.std():.4f}\\n")
                        f.write(f"R² Min:  {r2_values.min():.4f}\\n")
                        f.write(f"R² Max:  {r2_values.max():.4f}\\n")

            exported["summary_report"] = report_path

        except Exception as e:
            self.logger.error(f"Error writing summary report: {str(e)}")

        return exported

#!/usr/bin/env python3
"""
Test script for PyAMA core algorithms.

This script tests individual processing steps:
- Loading ND2 microscopy files
- Cell segmentation (logstd or cellpose)
- Background estimation
- Cell tracking (iou or btrack)
- Feature extraction
- Model fitting

Usage:
    python test_algo.py [--segmentation logstd|cellpose] [--tracking iou|btrack]
"""

import argparse
from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from pyama_core.io import load_microscopy_file, get_microscopy_time_stack
from pyama_core.processing.segmentation import (
    segment_cell_logstd,
    segment_cell_cellpose,
)
from pyama_core.processing.background import estimate_background
from pyama_core.processing.tracking import track_cell_iou, track_cell_btrack
from pyama_core.processing.extraction import extract_trace
from pyama_core.analysis.fitting import fit_model
from pyama_core.analysis.models import get_model


def print_progress(current, total, message):
    """Print progress updates every 30 frames."""
    if current % 30 == 0:
        print(f"  {message}: {current}/{total}")


def load_nd2_file(nd2_path):
    """Load an ND2 microscopy file and extract phase contrast and fluorescence channels.
    
    Returns:
        tuple: (phase_contrast_data, fluorescence_data, metadata) or (None, None, None) on error
    """
    print(f"Loading ND2 file: {nd2_path}")
    
    if not nd2_path.exists():
        print(f"❌ File not found: {nd2_path}")
        print("   Please update the path in the script or pass it as an argument")
        return None, None, None
    
    try:
        img, metadata = load_microscopy_file(nd2_path)
        
        print(f"✓ Loaded successfully")
        print(f"   Channels: {metadata.n_channels}")
        print(f"   Channel names: {metadata.channel_names}")
        print(f"   Timepoints: {metadata.n_frames}")
        print(f"   Image shape: {img.shape}")
        
        if metadata.n_channels < 2:
            print("❌ Need at least 2 channels (phase contrast + fluorescence)")
            return None, None, None
        
        # Extract phase contrast (channel 0) and fluorescence (channel 1)
        print("Extracting phase contrast (channel 0) and fluorescence (channel 1)...")
        phase_contrast = get_microscopy_time_stack(img, fov=0, channel=0).compute()
        fluorescence = get_microscopy_time_stack(img, fov=0, channel=1).compute()
        
        print(f"✓ Phase contrast shape: {phase_contrast.shape}")
        print(f"✓ Fluorescence shape: {fluorescence.shape}")
        
        return phase_contrast, fluorescence, metadata
        
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return None, None, None


def save_image_comparison(images, titles, output_path, frame_idx=100):
    """Save a side-by-side comparison of images."""
    fig, axes = plt.subplots(1, len(images), figsize=(4 * len(images), 4))
    if len(images) == 1:
        axes = [axes]
    
    for ax, img, title in zip(axes, images, titles):
        ax.imshow(img, cmap="gray" if "phase" in title.lower() or "segmentation" in title.lower() else "hot")
        ax.set_title(title)
        ax.axis("off")
    
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved: {output_path}")


def run_segmentation(phase_contrast, output_dir, algorithm="logstd"):
    """Run cell segmentation on phase contrast images.
    
    Args:
        phase_contrast: 3D array of phase contrast images (T, H, W)
        output_dir: Directory to save results
        algorithm: Either "logstd" or "cellpose"
    
    Returns:
        Segmentation mask array (T, H, W) of bool
    """
    print(f"\n{'='*60}")
    print(f"STEP 1: Cell Segmentation ({algorithm.upper()})")
    print(f"{'='*60}")
    
    # Choose algorithm
    if algorithm == "cellpose":
        segment_func = segment_cell_cellpose
        output_file = output_dir / "segmentation_cellpose.npy"
    else:
        segment_func = segment_cell_logstd
        output_file = output_dir / "segmentation_logstd.npy"
    
    # Load existing or compute new
    if output_file.exists():
        print(f"Loading existing segmentation from: {output_file}")
        segmentation = np.load(output_file)
    else:
        print(f"Running {algorithm} segmentation...")
        segmentation = np.empty_like(phase_contrast, dtype=bool)
        segment_func(phase_contrast, segmentation, print_progress)
        np.save(output_file, segmentation)
        print(f"✓ Saved to: {output_file}")
    
    # Visualize result
    frame_idx = min(100, len(phase_contrast) - 1)
    save_image_comparison(
        [phase_contrast[frame_idx], segmentation[frame_idx]],
        ["Phase Contrast", "Segmentation"],
        output_dir / "segmentation.png",
        frame_idx
    )
    
    return segmentation


def run_background_estimation(fluorescence, segmentation, output_dir):
    """Estimate background fluorescence using segmentation masks.
    
    Args:
        fluorescence: 3D array of fluorescence images (T, H, W)
        segmentation: 3D array of segmentation masks (T, H, W)
        output_dir: Directory to save results
    
    Returns:
        Background estimate array (T, H, W) of float32
    """
    print(f"\n{'='*60}")
    print("STEP 2: Background Estimation")
    print(f"{'='*60}")
    
    output_file = output_dir / "background_fluorescence.npy"
    
    if output_file.exists():
        print(f"Loading existing background from: {output_file}")
        background = np.load(output_file)
    else:
        print("Estimating background fluorescence...")
        background = np.empty_like(fluorescence, dtype=np.float32)
        estimate_background(fluorescence, segmentation, background, print_progress)
        np.save(output_file, background)
        print(f"✓ Saved to: {output_file}")
    
    # Visualize result
    frame_idx = min(100, len(fluorescence) - 1)
    vmin, vmax = fluorescence.min(), fluorescence.max()
    norm = TwoSlopeNorm(vmin=vmin, vcenter=vmin + 1000, vmax=vmax)
    
    fig, axes = plt.subplots(1, 2, figsize=(8, 4))
    im0 = axes[0].imshow(fluorescence[frame_idx], cmap="hot", norm=norm)
    axes[0].set_title("Original Fluorescence")
    axes[0].axis("off")
    
    im1 = axes[1].imshow(background[frame_idx], cmap="hot", norm=norm)
    axes[1].set_title("Estimated Background")
    axes[1].axis("off")
    
    plt.colorbar(im0, ax=axes[0], fraction=0.046, pad=0.04)
    plt.colorbar(im1, ax=axes[1], fraction=0.046, pad=0.04)
    
    fig.savefig(output_dir / "background_estimation.png", dpi=300)
    plt.close(fig)
    print(f"✓ Saved visualization: {output_dir / 'background_estimation.png'}")
    
    return background


def run_tracking(segmentation, output_dir, algorithm="iou"):
    """Track cells across time frames.
    
    Args:
        segmentation: 3D array of segmentation masks (T, H, W)
        output_dir: Directory to save results
        algorithm: Either "iou" or "btrack"
    
    Returns:
        Tracked labels array (T, H, W) of uint16
    """
    print(f"\n{'='*60}")
    print(f"STEP 3: Cell Tracking ({algorithm.upper()})")
    print(f"{'='*60}")
    
    # Choose algorithm
    if algorithm == "btrack":
        track_func = track_cell_btrack
        output_file = output_dir / "tracked_segmentation_btrack.npy"
    else:
        track_func = track_cell_iou
        output_file = output_dir / "tracked_segmentation_iou.npy"
    
    if output_file.exists():
        print(f"Loading existing tracking from: {output_file}")
        tracked = np.load(output_file)
    else:
        print(f"Running {algorithm} tracking...")
        tracked = np.zeros_like(segmentation, dtype=np.uint16)
        track_func(segmentation, tracked, progress_callback=print_progress)
        np.save(output_file, tracked)
        print(f"✓ Saved to: {output_file}")
    
    # Visualize tracking across time
    fig, axes = plt.subplots(1, 4, figsize=(12, 3))
    time_steps = np.linspace(0, len(tracked) - 1, 4, dtype=int)
    
    for ax, t in zip(axes, time_steps):
        # Highlight specific cells for visualization
        frame = tracked[t]
        highlighted = np.where(np.isin(frame, [50, 60, 70]), frame, 0)
        ax.imshow(highlighted, cmap="hot")
        ax.set_title(f"Frame {t}")
        ax.axis("off")
    
    fig.savefig(output_dir / "cell_tracking.png", dpi=300)
    plt.close(fig)
    print(f"✓ Saved visualization: {output_dir / 'cell_tracking.png'}")
    
    return tracked


def run_feature_extraction(fluorescence, tracked, output_dir):
    """Extract features (intensity, area, etc.) for each cell over time.
    
    Args:
        fluorescence: 3D array of fluorescence images (T, H, W)
        tracked: 3D array of tracked cell labels (T, H, W)
        output_dir: Directory to save results
    
    Returns:
        DataFrame with extracted features
    """
    print(f"\n{'='*60}")
    print("STEP 4: Feature Extraction")
    print(f"{'='*60}")
    
    output_file = output_dir / "cell_traces.csv"
    
    if output_file.exists():
        print(f"Loading existing traces from: {output_file}")
        traces_df = pd.read_csv(output_file, index_col=["cell", "time"])
    else:
        print("Extracting features for each cell...")
        # Create time array (assuming 6 frames per hour)
        times = np.arange(len(fluorescence)) / 6.0
        # No background correction for this test
        background = np.zeros_like(fluorescence, dtype=np.float32)
        
        traces_df = extract_trace(
            fluorescence, tracked, times, background,
            print_progress, background_weight=0.0
        )
        traces_df.to_csv(output_file)
        print(f"✓ Saved to: {output_file}")
    
    # Print summary
    n_cells = len(traces_df.index.get_level_values("cell").unique())
    time_min = traces_df.index.get_level_values("time").min()
    time_max = traces_df.index.get_level_values("time").max()
    
    print(f"\nExtraction summary:")
    print(f"   Total data points: {len(traces_df)}")
    print(f"   Unique cells: {n_cells}")
    print(f"   Time range: {time_min:.1f} - {time_max:.1f} hours")
    print(f"   Features: {list(traces_df.columns)}")
    
    # Show sample cells
    sample_cells = traces_df.index.get_level_values("cell").unique()[:3]
    print(f"\nSample cells {list(sample_cells)}:")
    for cell_id in sample_cells:
        cell_data = traces_df.loc[cell_id]
        intensity_min = cell_data["intensity_total"].min()
        intensity_max = cell_data["intensity_total"].max()
        print(f"   Cell {cell_id}: {len(cell_data)} timepoints, "
              f"intensity {intensity_min:.1f} - {intensity_max:.1f}")
    
    # Visualize features
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))
    sample_cells_all = traces_df.index.get_level_values("cell").unique()[:5]
    
    for cell_id in sample_cells_all:
        cell_data = traces_df.loc[cell_id]
        cell_data.plot(y="intensity_total", ax=axes[0], legend=False, 
                      color="green", alpha=0.5)
        cell_data.plot(y="area", ax=axes[1], legend=False, 
                      color="blue", alpha=0.5)
    
    axes[0].set_title("Intensity Total (Sample Cells)")
    axes[0].set_xlabel("Time [h]")
    axes[0].set_ylim(0, traces_df["intensity_total"].max() * 1.1)
    
    axes[1].set_title("Area (Sample Cells)")
    axes[1].set_ylim(0, traces_df["area"].max() * 1.1)
    axes[1].set_xlabel("Time [h]")
    
    fig.savefig(output_dir / "extracted_features.png", dpi=300)
    plt.close(fig)
    print(f"✓ Saved visualization: {output_dir / 'extracted_features.png'}")
    
    return traces_df


def run_model_fitting(traces_df, output_dir):
    """Fit a maturation model to cell intensity data.
    
    Args:
        traces_df: DataFrame with extracted features
        output_dir: Directory to save results
    """
    print(f"\n{'='*60}")
    print("STEP 5: Model Fitting")
    print(f"{'='*60}")
    
    # Pick a cell in the middle
    all_cells = traces_df.index.get_level_values("cell").unique()
    cell_id = all_cells[len(all_cells) // 2]
    
    print(f"Fitting maturation model to cell {cell_id}...")
    
    # Get data for this cell
    cell_data = traces_df.loc[cell_id]
    intensity = cell_data["intensity_total"].values
    time = cell_data.index.values
    
    print(f"   Time range: {time.min():.1f} - {time.max():.1f} hours")
    print(f"   Intensity range: {intensity.min():.1f} - {intensity.max():.1f}")
    print(f"   Data points: {len(intensity)}")
    
    # Fit model
    model = get_model("maturation")
    result = fit_model(model, time, intensity, model.DEFAULT_FIXED, model.DEFAULT_FIT)
    
    print(f"\n✓ Fitting completed:")
    print(f"   R² = {result.r_squared:.3f}")
    print(f"   Parameters:")
    for param_name, param in result.fitted_params.items():
        print(f"     {param_name} = {param.value:.3g}")
    
    # Generate fitted curve
    fitted_curve = model.eval(time, result.fixed_params, result.fitted_params)
    
    # Visualize
    fig, ax = plt.subplots(1, 1, figsize=(6, 4))
    ax.plot(time, intensity, label="data", linewidth=2, marker="o", markersize=3)
    ax.plot(time, fitted_curve, label="fit", linewidth=2)
    
    # Add parameter text
    param_text = f"$R^2$ = {result.r_squared:.3f}\n" + "\n".join(
        [f"{k} = {v.value:.3g}" for k, v in result.fitted_params.items()]
    )
    ax.text(0.05, 0.95, param_text, transform=ax.transAxes, fontsize=10,
            verticalalignment="top", 
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    
    ax.legend(loc="lower right")
    ax.set_xlabel("Time [h]")
    ax.set_ylabel("Intensity Total")
    ax.set_title(f"Maturation Model Fitting (Cell {cell_id})")
    
    fig.savefig(output_dir / "model_fitting.png", dpi=300)
    plt.close(fig)
    print(f"✓ Saved visualization: {output_dir / 'model_fitting.png'}")


def main():
    """Run the complete algorithm testing pipeline."""
    parser = argparse.ArgumentParser(
        description="Test PyAMA core algorithms",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use default algorithms (logstd segmentation, iou tracking)
  python test_algo.py

  # Use CellPose segmentation
  python test_algo.py --segmentation cellpose

  # Use btrack tracking
  python test_algo.py --tracking btrack

  # Use both alternative algorithms
  python test_algo.py --segmentation cellpose --tracking btrack
        """,
    )
    parser.add_argument(
        "--segmentation",
        choices=["logstd", "cellpose"],
        default="logstd",
        help="Segmentation algorithm (default: logstd)",
    )
    parser.add_argument(
        "--tracking",
        choices=["iou", "btrack"],
        default="iou",
        help="Tracking algorithm (default: iou)",
    )
    parser.add_argument(
        "--nd2-path",
        type=Path,
        default=Path("../data/test_sample.nd2"),
        help="Path to ND2 microscopy file (default: ../data/test_sample.nd2)",
    )
    args = parser.parse_args()
    
    print("="*60)
    print("PyAMA Algorithm Testing Pipeline")
    print("="*60)
    print(f"Segmentation: {args.segmentation}")
    print(f"Tracking: {args.tracking}")
    print(f"ND2 file: {args.nd2_path}")
    print()
    
    # Setup output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}\n")
    
    # Step 1: Load ND2 file
    phase_contrast, fluorescence, metadata = load_nd2_file(args.nd2_path)
    if phase_contrast is None:
        print("\n❌ Cannot proceed without valid ND2 file")
        return
    
    # Step 2: Segmentation
    segmentation = run_segmentation(phase_contrast, output_dir, args.segmentation)
    
    # Step 3: Background estimation
    background = run_background_estimation(fluorescence, segmentation, output_dir)
    
    # Step 4: Tracking
    tracked = run_tracking(segmentation, output_dir, args.tracking)
    
    # Step 5: Feature extraction
    traces_df = run_feature_extraction(fluorescence, tracked, output_dir)
    
    # Step 6: Model fitting
    run_model_fitting(traces_df, output_dir)
    
    # Summary
    print(f"\n{'='*60}")
    print("✓ All tests completed successfully!")
    print(f"{'='*60}")
    print(f"Results saved to: {output_dir}")
    n_cells = len(traces_df.index.get_level_values("cell").unique())
    print(f"Processed {n_cells} cells across {len(phase_contrast)} timepoints")
    print(f"Algorithms: segmentation={args.segmentation}, tracking={args.tracking}")


if __name__ == "__main__":
    main()

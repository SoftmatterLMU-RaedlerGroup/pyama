#!/usr/bin/env python3
"""
Visual testing script for PyAMA core algorithm functionality.
Shows input and output data explicitly instead of using assertions.
Demonstrates the complete processing pipeline from ND2 file to model fitting.
"""

from pathlib import Path
import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
import numpy as np
import pandas as pd
from pyama_core.io import load_microscopy_file, get_microscopy_time_stack
from pyama_core.processing.segmentation import segment_cell
from pyama_core.processing.background import estimate_background
from pyama_core.processing.tracking import track_cell
from pyama_core.processing.extraction import extract_trace
from pyama_core.analysis.fitting import fit_model
from pyama_core.analysis.models import get_model


def progress_callback(current, total, message):
    """Progress callback for processing functions."""
    if current % 30 == 0:
        print(f"  {message}: {current}/{total}")


def demonstrate_nd2_loading():
    """Demonstrate ND2 file loading and channel extraction."""
    print("=== ND2 File Loading Demo ===")

    # Configuration - update this path to your test ND2 file
    nd2_path = Path("../data/test_sample.nd2")

    if not nd2_path.exists():
        print(f"❌ ND2 file not found: {nd2_path}")
        print("Please update the nd2_path variable to point to your test ND2 file")
        return None, None, None

    try:
        print(f"Loading ND2 file: {nd2_path}")
        img, metadata = load_microscopy_file(nd2_path)

        print("✓ Successfully loaded ND2 file")
        print(f"  Channels: {metadata.n_channels}")
        print(f"  Channel names: {metadata.channel_names}")
        print(f"  Timepoints: {metadata.n_frames}")
        print(f"  Image shape: {img.shape}")

        # Extract phase contrast (typically channel 0) and fluorescence (channel 1)
        if metadata.n_channels < 2:
            print(
                "❌ ND2 file must have at least 2 channels (phase contrast + fluorescence)"
            )
            return None, None, None

        print("Extracting time stacks for channels 0 and 1...")
        phc_data = get_microscopy_time_stack(img, fov=0, channel=0).compute()
        fluor_data = get_microscopy_time_stack(img, fov=0, channel=1).compute()

        print(f"✓ Phase contrast shape: {phc_data.shape}")
        print(f"✓ Fluorescence shape: {fluor_data.shape}")

        return phc_data, fluor_data, metadata

    except Exception as e:
        print(f"❌ Error loading ND2 file: {e}")
        return None, None, None


def demonstrate_original_images(phc_data, fluor_data, output_dir):
    """Display original images from ND2 file."""
    print("\n=== Original Images Demo ===")

    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)
    time_idx = min(100, len(phc_data) - 1)  # Use frame 100 or last available frame

    print(f"Displaying frame {time_idx}")

    axs[0].imshow(phc_data[time_idx], cmap="gray")
    axs[0].set_title("Phase Contrast")
    axs[1].imshow(fluor_data[time_idx], cmap="hot")
    axs[1].set_title("Fluorescence")
    axs[0].axis("off")
    axs[1].axis("off")

    output_path = output_dir / "original_images.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved original images to: {output_path}")


def demonstrate_segmentation(phc_data, output_dir):
    """Demonstrate cell segmentation functionality."""
    print("\n=== Cell Segmentation Demo ===")

    seg_path = output_dir / "segmentation.npy"

    if seg_path.exists():
        print("Loading existing segmentation...")
        seg_data = np.load(seg_path)
        print(f"✓ Loaded segmentation from: {seg_path}")
    else:
        print("Running cell segmentation...")
        seg_data = np.empty_like(phc_data, dtype=bool)
        segment_cell(phc_data, seg_data, progress_callback)
        np.save(seg_path, seg_data)
        print(f"✓ Segmentation completed and saved to: {seg_path}")

    # Display segmentation result
    time_idx = min(100, len(phc_data) - 1)
    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)
    axs[0].imshow(phc_data[time_idx], cmap="gray")
    axs[0].set_title("Phase Contrast")
    axs[1].imshow(seg_data[time_idx], cmap="gray")
    axs[1].set_title("Segmentation")
    axs[0].axis("off")
    axs[1].axis("off")

    output_path = output_dir / "segmentation.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved segmentation visualization to: {output_path}")

    return seg_data


def demonstrate_background_estimation(fluor_data, seg_data, output_dir):
    """Demonstrate background estimation functionality."""
    print("\n=== Background Estimation Demo ===")

    background_path = output_dir / "background_fluorescence.npy"

    if background_path.exists():
        print("Loading existing background estimation...")
        background_data = np.load(background_path)
        print(f"✓ Loaded background data from: {background_path}")
    else:
        print("Running background estimation...")
        background_data = np.empty_like(fluor_data, dtype=np.float32)
        estimate_background(fluor_data, seg_data, background_data, progress_callback)
        np.save(background_path, background_data)
        print(f"✓ Background estimation completed and saved to: {background_path}")

    # Display background estimation result
    time_idx = min(100, len(fluor_data) - 1)
    fig, axs = plt.subplots(1, 2, figsize=(8, 4), constrained_layout=True)
    vmin = fluor_data.min()
    vmax = fluor_data.max()

    im0 = axs[0].imshow(
        fluor_data[time_idx],
        cmap="hot",
        norm=TwoSlopeNorm(vmin=vmin, vcenter=vmin + 1000, vmax=vmax),
    )
    axs[0].set_title("Original Fluorescence")

    im1 = axs[1].imshow(
        background_data[time_idx],
        cmap="hot",
        norm=TwoSlopeNorm(vmin=vmin, vcenter=vmin + 1000, vmax=vmax),
    )
    axs[1].set_title("Estimated Background")

    axs[0].axis("off")
    axs[1].axis("off")
    fig.colorbar(im0, ax=axs[0], fraction=0.046, pad=0.04)
    fig.colorbar(im1, ax=axs[1], fraction=0.046, pad=0.04)

    output_path = output_dir / "background_estimation.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved background estimation visualization to: {output_path}")

    return background_data


def demonstrate_cell_tracking(seg_data, output_dir):
    """Demonstrate cell tracking functionality."""
    print("\n=== Cell Tracking Demo ===")

    labeled_path = output_dir / "tracked_segmentation.npy"

    if labeled_path.exists():
        print("Loading existing tracking...")
        tracked_data = np.load(labeled_path)
        print(f"✓ Loaded tracking from: {labeled_path}")
    else:
        print("Running cell tracking...")
        tracked_data = np.zeros_like(seg_data, dtype=np.uint16)
        track_cell(seg_data, tracked_data, progress_callback=progress_callback)
        np.save(labeled_path, tracked_data)
        print(f"✓ Cell tracking completed and saved to: {labeled_path}")

    # Display tracking result
    fig, axs = plt.subplots(1, 4, figsize=(12, 3), constrained_layout=True)
    time_steps = np.linspace(0, len(tracked_data) - 1, 4, dtype=int)

    for i, t in enumerate(time_steps):
        fr = tracked_data[t]
        # Highlight a few specific cells for visualization
        highlighted = np.where(np.isin(fr, [50, 60, 70]), fr, 0)
        axs[i].imshow(highlighted, cmap="hot")
        axs[i].set_title(f"Frame {t}")
        axs[i].axis("off")

    output_path = output_dir / "cell_tracking.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved tracking visualization to: {output_path}")

    return tracked_data


def demonstrate_feature_extraction(fluorescence_data, tracked_data, output_dir):
    """Demonstrate feature extraction functionality."""
    print("\n=== Feature Extraction Demo ===")

    trace_path = output_dir / "cell_traces.csv"

    if trace_path.exists():
        print("Loading existing traces...")
        df = pd.read_csv(trace_path, index_col=["cell", "time"])
        print(f"✓ Loaded traces from: {trace_path}")
    else:
        print("Running feature extraction...")
        # Create time array (assuming 6 frames per hour, adjust as needed)
        times = np.arange(len(fluorescence_data)) / 6.0
        # Create zeros background for test (no background correction in demo)
        test_background = np.zeros_like(fluorescence_data, dtype=np.float32)
        df = extract_trace(fluorescence_data, tracked_data, times, test_background, progress_callback, background_weight=0.0)
        df.to_csv(trace_path)
        print(f"✓ Feature extraction completed and saved to: {trace_path}")

    print("Extracted features:")
    print(f"  Total traces: {len(df)}")
    print(f"  Unique cells: {len(df.index.get_level_values('cell').unique())}")
    print(
        f"  Time range: {df.index.get_level_values('time').min():.1f} - {df.index.get_level_values('time').max():.1f} hours"
    )
    print(f"  Available columns: {list(df.columns)}")

    # Display extracted features
    all_cells = df.index.get_level_values("cell").unique()
    sample_cells = all_cells[: min(5, len(all_cells))]  # Show up to 5 cells

    print(f"\nSample traces for cells {sample_cells[:3]}:")
    for cell in sample_cells[:3]:
        cell_data = df.loc[cell]
        print(
            f"  Cell {cell}: {len(cell_data)} timepoints, "
            f"intensity range: {cell_data['intensity_total'].min():.1f} - {cell_data['intensity_total'].max():.1f}"
        )

    # Visualize features
    fig, axs = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)

    for c in sample_cells:
        df.loc[c].plot(
            y="intensity_total", ax=axs[0], legend=False, color="green", alpha=0.5
        )
        df.loc[c].plot(y="area", ax=axs[1], legend=False, color="blue", alpha=0.5)

    axs[0].set_title("Intensity Total (Sample Cells)")
    axs[0].set_xlabel("Time [h]")
    axs[0].set_ylim(0, df["intensity_total"].max() * 1.1)
    axs[1].set_title("Area (Sample Cells)")
    axs[1].set_ylim(0, df["area"].max() * 1.1)
    axs[1].set_xlabel("Time [h]")

    output_path = output_dir / "extracted_features.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved feature visualization to: {output_path}")

    return df


def demonstrate_model_fitting(df, output_dir):
    """Demonstrate model fitting functionality."""
    print("\n=== Model Fitting Demo ===")

    all_cells = df.index.get_level_values("cell").unique()
    cell_id = all_cells[len(all_cells) // 2]  # Use middle cell

    print(f"Fitting maturation model to cell {cell_id}")

    y = df.loc[cell_id]["intensity_total"]
    t = df.loc[cell_id].index.values

    print(f"  Time range: {t.min():.1f} - {t.max():.1f} hours")
    print(f"  Intensity range: {y.min():.1f} - {y.max():.1f}")
    print(f"  Data points: {len(y)}")

    model = get_model("maturation")
    result = fit_model("maturation", t, y)

    print("✓ Fitting completed:")
    print(f"  R² = {result.r_squared:.3f}")
    print("  Parameters:")
    for param_name, param_value in result.fitted_params.items():
        print(f"    {param_name} = {param_value:.3g}")

    # Generate fitted curve
    y_pred = model.eval(t, result.fitted_params)

    # Visualize fitting result
    fig, axs = plt.subplots(1, 1, figsize=(6, 4), constrained_layout=True)
    axs.plot(t, y, label="data", linewidth=2, marker="o", markersize=3)
    axs.plot(t, y_pred, label="fit", linewidth=2)

    # Add parameter text
    param_text = f"$R^2$ = {result.r_squared:.3f}\n" + "\n".join(
        [f"{k} = {v:.3g}" for k, v in result.fitted_params.items()]
    )

    axs.text(
        0.05,
        0.95,
        param_text,
        transform=axs.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
    )

    axs.legend(loc="lower right")
    axs.set_xlabel("Time [h]")
    axs.set_ylabel("Intensity Total")
    axs.set_title(f"Maturation Model Fitting (Cell {cell_id})")

    output_path = output_dir / "model_fitting.png"
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f"✓ Saved model fitting visualization to: {output_path}")


def main():
    """Main testing pipeline with clear demonstrations."""
    print("PyAMA Algorithm Testing Pipeline")
    print("===============================")

    # Setup output directory
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    print(f"Output directory: {output_dir}")

    # Step 1: Load ND2 file
    phc_data, fluor_data, metadata = demonstrate_nd2_loading()
    if phc_data is None:
        print("\n❌ Cannot proceed without valid ND2 file")
        return

    # Step 2: Display original images
    demonstrate_original_images(phc_data, fluor_data, output_dir)

    # Step 3: Segmentation
    seg_data = demonstrate_segmentation(phc_data, output_dir)

    # Step 4: Background estimation
    background_data = demonstrate_background_estimation(fluor_data, seg_data, output_dir)

    # Step 5: Cell tracking
    tracked_data = demonstrate_cell_tracking(seg_data, output_dir)

    # Step 6: Feature extraction (using raw fluorescence, not background)
    df = demonstrate_feature_extraction(fluor_data, tracked_data, output_dir)

    # Step 7: Model fitting
    demonstrate_model_fitting(df, output_dir)

    print(f"\n{'='*50}")
    print("✓ All algorithm tests completed successfully!")
    print(f"Results saved to: {output_dir}")
    print(
        f"Processed {len(df.index.get_level_values('cell').unique())} cells "
        f"across {len(phc_data)} timepoints"
    )
    print("=" * 50)


if __name__ == "__main__":
    main()

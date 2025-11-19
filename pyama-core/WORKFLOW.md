# PyAMA-Core Processing Workflow

This document describes the complete processing workflow in PyAMA-Core, including what each step does, its inputs and outputs, and which channels from the microscopy data are used. This documentation is intended to help with implementing the workflow as a plugin in third-party software, where actual implementations may differ.

## Overview

The PyAMA-Core processing workflow processes time-lapse microscopy images through five sequential steps to extract cell traces with quantitative features. The workflow operates on individual Fields of View (FOVs) and processes data in batches for efficiency.

**Processing Order:**

1. **Copying** - Extract frames from microscopy files (ND2/CZI) to disk
2. **Segmentation** - Identify cell boundaries using phase contrast images
3. **Correction** - Apply background correction to fluorescence channels
4. **Tracking** - Track cells across time points using consistent cell IDs
5. **Extraction** - Extract quantitative features and generate trace CSV files

## Input Requirements

**Microscopy Data:**

- Input format: ND2 or CZI files containing time-lapse microscopy images
- Multiple FOVs (Fields of View) can be processed in parallel
- Each FOV contains multiple time frames and multiple channels

**Channel Configuration:**

- **Phase Contrast (PC) Channel**: Required for segmentation. One channel specified for cell boundary detection.
- **Fluorescence (FL) Channels**: Optional, one or more channels specified for feature extraction. Can be processed independently.

**Processing Context:**

- Output directory path
- Channel selections (which PC channel, which FL channels)
- Feature list to extract per channel
- Processing parameters (optional)
- Time units (typically "min" for minutes)

## Workflow Steps

### Step 1: Copying Service

**Purpose:** Extract raw image frames from the microscopy file format (ND2/CZI) and save them as NumPy memory-mapped arrays on disk for efficient access by subsequent steps.

**Input:**

- Microscopy file path (ND2 or CZI format)
- FOV index range to process
- Channel configuration (PC channel ID and FL channel IDs)

**Channels Used:**

- Phase contrast channel (PC): One channel specified in the configuration
- Fluorescence channels (FL): Zero or more channels specified in the configuration

**Processing:**

- For each FOV and each specified channel:
  1. Load frames sequentially from the microscopy file
  2. Create a memory-mapped NumPy array file: `{basename}_fov_{fov:03d}_{pc|fl}_ch_{channel_id}.npy`
  3. Write all time frames `(T, H, W)` where:
     - `T` = number of time frames
     - `H` = image height in pixels
     - `W` = image width in pixels
  4. Data type: `uint16` for raw microscopy pixel values

**Output:**

- Phase contrast stack: `{basename}_fov_{fov:03d}_pc_ch_{pc_id}.npy` - 3D array `(T, H, W)` of `uint16`
- Fluorescence stacks (one per channel): `{basename}_fov_{fov:03d}_fl_ch_{fl_id}.npy` - 3D array `(T, H, W)` of `uint16`

**Notes:**

- Runs sequentially per batch (not parallelized) to avoid file I/O bottlenecks
- Files are saved as memory-mapped arrays for efficient random access
- Existing files are detected and skipped (allows resuming interrupted workflows)

---

### Step 2: Segmentation Service

**Purpose:** Identify cell boundaries in each frame using phase contrast microscopy images. The segmentation produces binary masks where pixels are marked as foreground (cells) or background.

**Input:**

- Phase contrast image stack from Step 1: `{basename}_fov_{fov:03d}_pc_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `uint16` pixel values

**Channels Used:**

- Phase contrast channel (PC): Single channel specified in configuration

**Processing Algorithm (LOG-STD Method):**
For each time frame `t` in `[0, T-1]`:

1. **Compute Log Standard Deviation:**
   - Apply uniform filter to compute local mean and variance in a sliding window
   - Calculate log standard deviation: `logstd = 0.5 * log(variance)` where variance > 0
   - Window size configurable (default uses small neighborhood for efficiency)

2. **Threshold Selection:**
   - Build histogram of log-STD values
   - Automatically select threshold from histogram (typically at valley between modes)
   - Creates binary mask: `binary = logstd > threshold`

3. **Morphological Cleanup:**
   - Fill holes in binary mask
   - Apply binary opening (erosion then dilation) to remove small noise
   - Apply binary closing (dilation then erosion) to close gaps
   - Iterations and structure size are configurable (default: size=7, iterations=3)

**Output:**

- Binary segmentation mask: `{basename}_fov_{fov:03d}_seg_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `bool`
  - `True` pixels = foreground (cells)
  - `False` pixels = background

**Notes:**

- LOG-STD method is effective for phase contrast images because cell boundaries produce local intensity variations
- Morphological cleanup reduces noise and artifacts
- The segmentation is frame-by-frame (no temporal information used)

---

### Step 3: Correction Service

**Purpose:** Estimate background fluorescence for each frame using tiled interpolation. The estimated background is saved for later correction during feature extraction. This allows flexible background correction with configurable weights.

**Input:**

- Binary segmentation mask from Step 2: `{basename}_fov_{fov:03d}_seg_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `bool`
- Raw fluorescence stacks from Step 1: `{basename}_fov_{fov:03d}_fl_ch_{fl_id}.npy` (one per FL channel)
  - Format: 3D array `(T, H, W)` of `uint16`

**Channels Used:**

- Phase contrast channel (PC): Used indirectly via segmentation mask (indicates foreground regions)
- Fluorescence channels (FL): Each specified FL channel is processed independently

**Processing Algorithm (Tiled Interpolation Method):**
For each fluorescence channel and each time frame `t`:

1. **Mask Foreground:**
   - Dilate the segmentation mask to exclude foreground regions from background estimation
   - Create masked image where foreground pixels are excluded (masked out)
   - This prevents cellular fluorescence from influencing background estimates

2. **Compute Tile Medians:**
   - Divide the frame into overlapping tiles (typically 50-100 pixel tiles)
   - For each tile, compute the median pixel value from background (non-masked) pixels
   - If tile has insufficient background pixels, interpolate from neighboring tiles
   - Results in a 2D grid of tile median values

3. **Interpolate Background Surface:**
   - Use bicubic spline interpolation (`scipy.interpolate.RectBivariateSpline`) to create a smooth background surface from tile medians
   - Interpolate to full frame resolution `(H, W)`
   - Produces estimated background fluorescence per pixel
   - Output the interpolated background (correction step is saved for later processing)

**Output:**

- Background interpolation stack: `{basename}_fov_{fov:03d}_fl_background_ch_{fl_id}.npy`
  - Format: 3D array `(T, H, W)` of `float32`
  - Estimated background fluorescence per pixel (correction is saved for later)

**Notes:**

- Each fluorescence channel is processed independently
- Temporal independence: each frame is estimated using only that frame's data (not temporal smoothing)
- Tiled approach handles spatially varying background (common in fluorescence microscopy)
- Background stacks are preferred for feature extraction, but raw stacks can be used as fallback

---

### Step 4: Tracking Service

**Purpose:** Track cells across time frames by assigning consistent cell IDs throughout the time series. This links the same physical cell across different frames, enabling temporal analysis of cell properties.

**Input:**

- Binary segmentation mask from Step 2: `{basename}_fov_{fov:03d}_seg_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `bool`

**Channels Used:**

- Phase contrast channel (PC): Used indirectly via segmentation mask (tracks segmentation regions)

**Processing Algorithm (IoU-based Hungarian Assignment):**
The tracking algorithm processes frames sequentially:

1. **Extract Regions per Frame:**
   - For frame `t`, apply connected component labeling to binary segmentation
   - Extract properties for each connected region:
     - Area (pixel count)
     - Bounding box `(y0, x0, y1, x1)`
     - Pixel coordinates for all pixels in the region
   - Filter regions by size (optional `min_size`, `max_size` parameters)
   - Store regions with temporary frame-specific labels

2. **Build IoU Cost Matrix:**
   - For frame `t`, compare each region from frame `t` with each region from frame `t-1`
   - Compute Intersection over Union (IoU) using bounding boxes:
     - `IoU = intersection_area / union_area`
   - Build cost matrix where each entry is `1 - IoU` (lower is better match)
   - Regions with `IoU < min_iou` threshold are considered non-matching

3. **Solve Assignment Problem:**
   - Use Hungarian algorithm (`scipy.optimize.linear_sum_assignment`) to find optimal one-to-one assignment
   - Maximizes total IoU (minimizes cost) between consecutive frames
   - Each region in frame `t` is assigned to at most one region in frame `t-1`

4. **Assign Consistent Cell IDs:**
   - Initialize: frame 0 regions get new cell IDs (1, 2, 3, ...)
   - For each subsequent frame:
     - Matched regions inherit the cell ID from their assigned previous frame region
     - Unmatched regions (new cells) get new cell IDs
     - Unmatched previous regions (disappeared cells) terminate that cell's trace

5. **Write Labeled Stack:**
   - Create labeled image where each pixel value is the cell ID
   - `labeled[t, y, x] = cell_id` where cell exists, `0` otherwise
   - Maintain spatial resolution: `(T, H, W)`

**Output:**

- Labeled tracking stack: `{basename}_fov_{fov:03d}_seg_labeled_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `uint16`
  - Pixel values: `0` = background, `1...N` = cell IDs (consistent across frames)

**Notes:**

- IoU-based matching is robust to cell movement and shape changes
- Hungarian algorithm ensures optimal global assignment (not just greedy matching)
- Min IoU threshold (default 0.1) filters out poor matches
- Cell IDs persist across frames for cells that persist, enabling temporal trace extraction

---

### Step 5: Extraction Service

**Purpose:** Extract quantitative features for each tracked cell at each time point and generate a CSV file with temporal traces. Features are computed from both phase contrast and fluorescence images.

**Input:**

- Labeled tracking stack from Step 4: `{basename}_fov_{fov:03d}_seg_labeled_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `uint16` (cell IDs)
- Phase contrast stack from Step 1: `{basename}_fov_{fov:03d}_pc_ch_{pc_id}.npy`
  - Format: 3D array `(T, H, W)` of `uint16`
- Background (or raw) fluorescence stacks: `{basename}_fov_{fov:03d}_fl_background_ch_{fl_id}.npy` or `{basename}_fov_{fov:03d}_fl_ch_{fl_id}.npy`
  - Format: 3D array `(T, H, W)` of `float32` (background) or `uint16` (raw)
- Feature configuration: List of feature names to extract per channel
- Time points: Optional time metadata from microscopy file (converted to minutes)

**Channels Used:**

- Phase contrast channel (PC): Extract morphological features (area, aspect ratio, etc.)
- Fluorescence channels (FL): Extract intensity and fluorescence-based features (intensity_total, intensity_mean, etc.)

**Processing Algorithm:**
For each time frame `t`:

1. **Extract Features per Cell:**
   - For each unique cell ID `c` in the labeled frame:
     - Create binary mask: `mask = (seg_labeled[t] == c)`
     - Load both raw fluorescence and background data (if available)
     - Extract features using the mask and corresponding image pixels
     - Features computed depend on the channel:
       - **Phase contrast features:** Morphological properties (area, perimeter, aspect ratio, etc.)
       - **Fluorescence features:** Intensity statistics (total, mean, max, median, std, etc.)
       - **Background correction:** For `intensity_total`, computes `(image - weight * background)` where weight is configurable via `params.background_weight` (default: 1.0, clamped to [0, 1])

2. **Feature Categories:**
   Common features include:
   - **Base fields** (always present):
     - `cell`: Cell ID (consistent across frames)
     - `frame`: Time frame index (0-based)
     - `time`: Time in minutes
     - `good`: Quality flag (boolean)
     - `position_x`, `position_y`: Cell centroid coordinates (pixels)
     - `bbox_x0`, `bbox_y0`, `bbox_x1`, `bbox_y1`: Bounding box coordinates

   - **Morphological features** (from PC channel):
     - `area`: Number of pixels in cell
     - `perimeter`: Cell boundary length
     - `aspect_ratio`: Ratio of major to minor axis
     - And others...

   - **Intensity features** (from FL channels, per channel):
     - `intensity_total`: Background-corrected total intensity computed as `(image - weight * background)` summed over cell pixels
     - `intensity_mean`: Mean pixel value
     - `intensity_max`: Maximum pixel value
     - `intensity_median`: Median pixel value
     - `intensity_std`: Standard deviation
     - And others...

3. **Combine Features:**
   - Extract features from PC channel if configured
   - Extract features from each FL channel if configured
   - For fluorescence features: if background data is available, it's loaded alongside raw data
   - Background correction weight is read from `ProcessingContext.params["background_weight"]` (default: 1.0, validated and clamped to [0, 1])
   - Merge all feature columns into a single DataFrame
   - Feature columns are suffixed with channel ID: `{feature_name}_ch_{channel_id}` (e.g., `intensity_total_ch_1`, `area_ch_0`)
   - This allows downstream analysis to identify which channel each feature came from

**Configuration Parameters:**
- `background_weight` (in `ProcessingContext.params`): Weight for background subtraction in fluorescence feature extraction
  - Type: `float`
  - Default: `1.0` (full background subtraction)
  - Range: `[0.0, 1.0]` (automatically clamped if outside range)
  - Usage: Controls the strength of background correction; `0.0` = no correction, `1.0` = full correction
  - Example: Set `params={"background_weight": 1.0}` to apply full background correction

4. **Filter Traces:**
   - Remove short traces (cells that appear in too few frames)
   - Remove border cells (cells touching image edges within a border width, default 50 pixels)
   - Filtering ensures only high-quality, complete traces are included

5. **Generate CSV:**
   - Create one CSV file per FOV: `{basename}_fov_{fov:03d}_traces.csv`
   - Each row = one cell at one time point
   - Columns: base fields + all feature columns (suffixed by channel ID)
   - Sorted by `[cell, frame, time]`

**Output:**

- Trace CSV file: `{basename}_fov_{fov:03d}_traces.csv`
  - Format: Comma-separated values
  - Columns include: `fov`, `cell`, `frame`, `time`, `good`, `position_x`, `position_y`, `bbox_x0`, `bbox_y0`, `bbox_x1`, `bbox_y1`, plus all requested features per channel
  - Each row represents one cell at one time point
  - Feature columns are suffixed: `{feature}_ch_{channel_id}`

**Notes:**

- Features are extracted per-channel, allowing independent analysis of different fluorescence markers
- Corrected fluorescence stacks are preferred (if available) over raw stacks for better accuracy
- Time is converted to minutes from original metadata (milliseconds) or defaulted to frame indices
- Filtered traces ensure only complete, high-quality cell trajectories are included in analysis

---

## Output Structure

After completing the workflow, the output directory contains:

```
output_dir/
├── processing_results.yaml          # Metadata: channels, paths, parameters
├── fov_000/
│   ├── {basename}_fov_000_pc_ch_{pc_id}.npy          # Raw PC stack
│   ├── {basename}_fov_000_fl_ch_{fl_id}.npy          # Raw FL stacks (one per channel)
│   ├── {basename}_fov_000_seg_ch_{pc_id}.npy         # Binary segmentation
│   ├── {basename}_fov_000_seg_labeled_ch_{pc_id}.npy # Tracked cell labels
│   ├── {basename}_fov_000_fl_background_ch_{fl_id}.npy # Background interpolation stacks (one per channel)
│   └── {basename}_fov_000_traces.csv                 # Combined feature traces
├── fov_001/
│   └── ...
└── ...
```

## Batch Processing

The workflow processes FOVs in batches to manage memory and I/O:

1. **Batch Creation:** FOVs are divided into contiguous batches (e.g., batch_size=2 processes 2 FOVs at a time)

2. **Sequential Copying:** For each batch:
   - Copying Service runs sequentially for all FOVs in the batch
   - This avoids file I/O bottlenecks

3. **Parallel Processing:** After copying:
   - Batch FOVs are split across worker threads (e.g., n_workers=2)
   - Each worker processes Steps 2-5 (Segmentation, Correction, Tracking, Extraction) independently
   - Workers operate on different FOVs in parallel

4. **Context Merging:** After each batch completes:
   - Worker contexts (containing result paths) are merged into the main context
   - Results are tracked in the ProcessingContext dataclass

## Channel Usage Summary

| Step | Phase Contrast (PC) | Fluorescence (FL) | Output Type |
|------|---------------------|-------------------|-------------|
| **1. Copying** | ✓ Required (one channel) | ✓ Optional (zero or more channels) | Raw image stacks |
| **2. Segmentation** | ✓ Required (uses PC image) | ✗ Not used | Binary masks |
| **3. Correction** | ✗ Indirect (uses segmentation mask from PC) | ✓ Required (uses FL images) | Background-corrected FL stacks |
| **4. Tracking** | ✗ Indirect (uses segmentation masks) | ✗ Not used | Labeled cell IDs |
| **5. Extraction** | ✓ Optional (if PC features requested) | ✓ Optional (if FL features requested) | Feature traces CSV |

## Implementation Notes for Plugin Development

When implementing this workflow as a plugin:

1. **File Format Flexibility:** The workflow can work with any image format, not just ND2/CZI. You can implement your own file readers that produce `(T, H, W)` arrays.

2. **Algorithm Replacements:** Each step's algorithm (LOG-STD segmentation, tiled background correction, IoU tracking) can be replaced with alternative implementations as long as:
   - Input/output shapes and data types match
   - Segmentation produces binary masks `(T, H, W)` bool
   - Tracking produces labeled IDs `(T, H, W)` uint16
   - Extraction produces CSV with consistent column naming

3. **Feature Extraction:** Feature lists are configurable. You can:
   - Implement custom feature extractors
   - Select subset of features per channel
   - Add channel-specific feature naming

4. **Memory Management:** The workflow uses memory-mapped arrays to handle large time-lapse datasets. Consider:
   - Memory-mapped file I/O for large stacks
   - Frame-by-frame processing where possible
   - Progress callbacks for user feedback

5. **Parallelization:** The workflow supports multi-threaded processing:
   - Copying: Sequential per batch (I/O bound)
   - Steps 2-5: Parallel across FOVs (CPU bound)
   - Adjust worker counts based on hardware capabilities

6. **Cancellation Support:** All steps support cancellation events:
   - Check for cancellation before processing each frame
   - Clean up partial files on cancellation
   - Preserve completed FOVs for resuming

7. **Data Types:**
   - Raw images: `uint16`
   - Binary masks: `bool`
   - Corrected fluorescence: `float32`
   - Cell labels: `uint16` (supports up to 65,535 cells per FOV)
   - Traces CSV: Standard CSV with floating-point feature values

## Key Algorithm Characteristics

- **Segmentation:** LOG-STD thresholding with morphological cleanup - effective for phase contrast
- **Correction:** Tiled interpolation background estimation - handles spatially varying background
- **Tracking:** IoU-based Hungarian assignment - robust to cell movement and shape changes
- **Extraction:** Per-cell, per-frame feature computation with temporal trace filtering

This workflow design balances accuracy, performance, and flexibility for quantitative time-lapse cell analysis.

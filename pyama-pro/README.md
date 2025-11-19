# How to Use PyAMA-Pro

This guide walks you through using the PyAMA-Pro GUI for microscopy image analysis.

## Processing Tab

### Step 1: Load Microscopy File

- Click on the **Processing** tab
- Click **Browse** next to "Microscopy File:" to select your ND2 file
- The file name will appear once loaded

### Step 2: Configure Channels

**Phase Contrast Configuration:**

- Select the **Phase Contrast Channel** from the dropdown
- In the **Phase Contrast Features** list, **multi-select** (Ctrl+Click or Shift+Click) the features you want (e.g., `area`, `aspect_ratio`)

**Fluorescence Configuration:**

- In the **Fluorescence** section, select a channel from the dropdown
- Select a feature from the feature dropdown
- Click **Add** to add the channel-feature combination
- Repeat to add multiple channel-feature pairs
- To remove a combination, select it in the "Fluorescence Features" list and click **Remove Selected**

### Step 3: Set Output Folder

- Click **Browse** next to "Save Directory:" to select where processed results will be saved

### Step 4: Configure Parameters

- Check **Set parameters manually** checkbox to show the parameter table
- Default values are set automatically when a microscopy file is loaded
- Modify parameters as needed:
  - `fov_start`: Starting FOV index (default: 0)
  - `fov_end`: Ending FOV index (default: -1 -> automatically uses last FOV after metadata loads)
  - `batch_size`: Number of FOVs to process in each batch (default: 2)
  - `n_workers`: Number of parallel worker threads (default: 2)
  - `background_weight`: Weight for background subtraction in fluorescence feature extraction (default: 1.0)
    - Range: 0.0 to 1.0 (automatically clamped if outside range)
    - 0.0 = no background correction (raw intensity values)
    - 1.0 = full background correction (full subtraction)
    - Values between 0 and 1 apply partial correction

### Step 5: Run Workflow

- Click **Start Complete Workflow**
- Progress bar will appear during processing
- Click **Cancel** button if you need to stop the workflow
- Wait for completion; status message will show when finished

## Visualization Tab (Optional)

The visualization tab should be used before merging CSV files for quality control and trace inspection.

### Step 1: Load Project

- Click on the **Visualization** tab
- Click **Load Folder** button
- Select the folder containing processing results (same as "Save Directory" from processing)
- Project details will display showing FOV count and available data types

### Step 2: Configure Visualization

- Use the **FOV** spinbox to select which field of view to visualize (range: 0 to max_FOV-1)
- Select channels from the **channel list** (multi-select enabled):
  - Generally select: `pc_xxx`, `seg_labeled_xxx`, `fl_background_xxx`
  - Notice the `ch_x` suffix - only load the fluorescence channels you need
- Click **Start Visualization** button
- Wait for data to load (progress bar will show)

### Step 3: Navigate Images

- Use the **Data Type** dropdown to switch between loaded channels
- Use navigation buttons to move through time points:
  - **<** / **>** to go back/forward 1 frame
  - **<<** / **>>** to go back/forward 10 frames
- The frame label shows current position (e.g., "Frame 1/100")

### Step 4: Inspect Traces

- Change the **Feature** dropdown to select which feature to plot (e.g., `intensity_total`, `area`)
- Traces are shown in pages, with 10 traces per page in the list below the plot
- Click on trace IDs in the list to select them
- **Right-click** on trace IDs to toggle quality (good/bad)
- Quality indicators:
  - Blue traces: Good quality
  - Green traces: Bad quality (hidden from plot)
  - Red trace: Currently active/highlighted trace
- Selected traces show with a red circle overlay on the image marking cell position

### Step 5: Save Inspected Data

- After inspecting and marking traces as good/bad, click **Save Inspected CSV**
- This saves a file with `_inspected` suffix (e.g., `traces_inspected.csv`)
- The inspected file will be loaded automatically the next time you load the project
- Only "good" traces will be included in merged results

## Merging CSV Files

### Step 1: Assign FOVs to Samples

- In the **Processing** tab, locate the **Assign FOVs** section (on the right side)
- Click **Add Sample** button to add a new row to the table
- Fill in the table:
  - **Sample Name** column: Enter sample name (e.g., `sample1`)
  - **FOVs** column: Enter FOV range (e.g., `0-5` for FOVs 0 through 5, or `0, 2, 4-6` for specific FOVs)
- Repeat to add multiple samples
- Use **Remove Selected** to delete rows

### Step 2: Save Sample Configuration

- Click **Save to YAML** button
- Choose a location and filename (e.g., `samples.yaml`)
- This saves your sample definitions for later use

### Step 3: Configure Merge Settings

**Optional: Load existing sample configuration**

- Click **Load from YAML** if you want to load previously saved samples

**Set file paths:**

- Click **Browse** next to **Sample YAML:** and select your samples.yaml file
- Click **Browse** next to **Processing Results YAML:** and select `processing_results.yaml` (found in your save folder)
- Click **Browse** next to **Output folder:** and select where merged results should be saved (generally same as save folder)

### Step 4: Run Merge

- Click **Run Merge** button
- Wait for completion; status message will show when finished
- Merged CSV files will be created in the output folder with sample names

## Analysis Tab

### Step 1: Load Data

- Click on the **Analysis** tab
- Click **Load CSV** button
- Select your merged traces CSV file (or inspected traces file)
- All traces and their mean will be plotted
- The plot shows "All Sequences (X cells)" where X is the number of cells

**Optional: Load Fitted Results**

- Click **Load Fitted Results** button to load previously fitted data
- Select a fitted results CSV file (e.g., `traces_fitted_maturation.csv`)
- The model dropdown will automatically update to match the model type from the CSV
- The parameter table will automatically show the correct parameters for that model
- This allows you to review or compare results from different fitting runs

### Step 2: Select Model

- In the **Fitting** section, select a **Model** from the dropdown (e.g., `trivial`, `maturation`)
- The parameter table will update automatically with default values for the selected model
- Check **Set parameters manually** checkbox to enable manual editing
- Adjust parameter values and bounds in the table as needed

### Step 3: Run Fitting

- Click **Start Fitting** button
- Progress bar will appear during fitting
- Wait for fitting to complete
- The fitting result will be saved automatically with `_fitted` suffix as CSV (e.g., `traces_fitted.csv`)
- Status message will show when finished

### Step 4: Review Results

**Fitting Quality Panel (middle panel):**

- The **Fitted Traces** plot displays raw data (blue) and fitted curve (red) for selected cells
- **Quality Statistics** label shows percentages at the top:
  - Good: R² > 0.9
  - Mid: 0.7 < R² ≤ 0.9
  - Bad: R² ≤ 0.7
- **Trace Selection** list shows traces grouped by FOV with pagination
- Traces are color-coded in the list based on fit quality:
  - Green: Good fits (R² > 0.9)
  - Orange: Mid fits (0.7 < R² ≤ 0.9)
  - Red: Poor fits (R² ≤ 0.7)
- Click on a trace in the list to view its fit in the plot above
- Use **Previous** and **Next** buttons to navigate between FOVs
- Each page shows all cells from the current FOV

### Step 5: View Parameters

**Parameter Analysis Panel (right panel):**

- Select a **Parameter** from the dropdown to view histograms
- The histogram shows parameter distribution across all fitted cells
- Check **Good fits only (R² > 0.9)** checkbox to filter to high-quality fits
- For dual parameter analysis, select X and Y parameters from the dropdowns to view scatter plots
- Click **Save All Plots** to save parameter histograms and scatter plots as PNG files

## Tips

- **Default Parameters**: Default parameter values are set automatically when files are loaded; adjust manually only when needed
- **FOV Processing**: By default, all FOVs are processed (`fov_start=0`, `fov_end=-1` which resolves to the last FOV after metadata loads); adjust these values to process a subset
- **Multi-Selection**: Use Ctrl+Click or Shift+Click to select multiple items in lists
- **Inspected Files**: Save inspected traces after reviewing to ensure only high-quality traces are used in analysis
- **Workflow Order**: Complete processing → visualization/inspection → merging → analysis for best results
- **Quality Control**: Mark traces as "bad" during visualization to exclude them from merged results
- **Parameter Exploration**: Navigate through FOVs in the quality panel to explore different fits and validate your model
- **File Locations**: Keep track of where your processing_results.yaml and samples.yaml files are saved for easy access
- **Model Detection**: When loading fitted results, the model dropdown updates automatically to match the saved model type
- **FOV Navigation**: Use Previous/Next buttons in the quality panel to browse traces grouped by FOV for easier quality assessment

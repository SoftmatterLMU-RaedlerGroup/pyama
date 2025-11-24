# How to Use PyAMA-Air

PyAMA-Air provides both a modern GUI and a command-line interface for configuring and running PyAMA workflows without opening the full Qt application.

## GUI Application

### Launching the GUI

```bash
pyama-air gui
```

This opens a modern GUI window with two main wizards:

### Workflow Wizard

1. **Click "Workflow Wizard"** from the Tools menu or main window
2. Follow the step-by-step configuration:
   - **Select ND2 File**: Browse and select your microscopy file
   - **Configure Channels**: Select phase contrast and fluorescence channels
   - **Select Features**: Choose features to extract (automatically discovered from pyama-core)
   - **Set Output Directory**: Choose where to save results
   - **Configure Parameters**: Adjust FOV range, batch size, and worker count
   - **Review Summary**: Check all settings before execution
3. **Click "Start Workflow"** to begin processing
4. Monitor progress through the progress bar
5. View results in the output directory

### Merge Wizard

1. **Click "Merge Wizard"** from the Tools menu or main window
2. Follow the step-by-step configuration:
   - **Assign FOVs**: Add samples and their FOV ranges (e.g., `sample1`, `0-5`)
   - **Load Processing Results**: Select the `processing_results.yaml` file
   - **Set Output Directory**: Choose where to save merged CSVs
3. **Click "Run Merge"** to combine CSV files
4. Merged files will be created with sample names

## Command Line Interface

### Basic Commands

```bash
# Launch interactive CLI
pyama-air cli

# Or run specific commands directly
pyama-air cli workflow
pyama-air cli merge
```

### Workflow Command

```bash
pyama-air cli workflow
```

The workflow command prompts you for:

1. **ND2 File Path**: Enter the path to your microscopy file
2. **Phase Contrast Channel**: Select channel index from available channels
3. **Phase Contrast Features**: Enter comma-separated features (e.g., `area,aspect_ratio`)
4. **Fluorescence Channels**: Repeat for each fluorescence channel:
   - Channel index
   - Features to extract
5. **Output Directory**: Where to save results
6. **FOV Range**: Starting and ending FOV indices
7. **Batch Size**: Number of FOVs per batch
8. **Number of Workers**: Parallel worker threads

Features are automatically discovered from pyama-core. Available features include:

- **Phase contrast**: `area`, `aspect_ratio`
- **Fluorescence**: `intensity_total`

### Merge Command

```bash
pyama-air cli merge
```

The merge command prompts you for:

1. **Sample Definitions**: Enter sample names and FOV ranges
   - Format: `sample_name: fov_range` (e.g., `sample1: 0-5`)
   - Enter multiple samples separated by newlines
   - Enter "done" when finished
2. **Sample YAML Path**: Where to save/load sample configuration
3. **Processing Results YAML**: Path to `processing_results.yaml`
4. **Output Directory**: Where to save merged CSVs

### Help Commands

```bash
# Get help for main commands
pyama-air --help

# Get help for CLI subcommands
pyama-air cli --help
pyama-air cli workflow --help
pyama-air cli merge --help

# Get help for GUI
pyama-air gui --help
```

## Features

### Dynamic Feature Discovery

Both CLI and GUI automatically discover available features from the PyAMA core library:

- No need to hardcode feature names
- Automatically picks up custom features if added to pyama-core
- Fallback to defaults if invalid features are specified

### Real-time Validation

- Immediate feedback on configuration validity
- Clear error messages for invalid inputs
- Automatic range checking for FOV selections

### Progress Indicators

Visual feedback during workflow execution for both GUI and CLI interfaces.

## Tips

- **File Paths**: Use absolute paths or paths relative to your current directory
- **FOV Ranges**: Specify as single indices (e.g., `0`) or ranges (e.g., `0-5`)
- **Batch Processing**: Larger batch sizes use more memory but may be faster
- **Worker Threads**: Match the number of workers to your CPU cores for optimal performance
- **Feature Selection**: Check available features before configuration using `--help` commands
- **Sample Definitions**: Save your sample YAML file for reuse across experiments

## Integration with PyAMA-Pro

PyAMA-Air complements PyAMA-Pro:

- **Use Air for**: Quick configuration, testing parameters, automated workflows
- **Use Pro for**: Full visualization, trace inspection, detailed analysis

Both tools produce compatible outputs and can be used interchangeably for different stages of your workflow.

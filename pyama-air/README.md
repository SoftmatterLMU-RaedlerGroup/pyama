# pyama-air

`pyama-air` provides both conversational command-line helpers and a modern GUI that guide you through
common PyAMA tasks without opening the main Qt application.

## Installation

```bash
# Install pyama-air with GUI support
uv pip install -e pyama-air/
```

## Usage

### GUI Application

Launch the modern GUI interface:

```bash
pyama-air gui
```

The GUI provides two main wizards:

- **Workflow Wizard**: Step-by-step configuration for PyAMA processing workflows
- **Merge Wizard**: Interactive sample configuration and CSV merging

### Command Line Interface

For automation and scripting, use the CLI:

```bash
# Workflow configuration and execution
pyama-air cli workflow

# Sample configuration and CSV merging
pyama-air cli merge
```

The CLI commands provide the same functionality as the GUI but through text prompts:

- `pyama-air cli workflow` asks for an ND2 file, phase-contrast and fluorescence channel
  selections, feature options, time units, and batching parameters before kicking off
  the full processing workflow. Features are automatically discovered from the PyAMA
  core library.
- `pyama-air cli merge` mirrors the merge panel from the Qt app, prompting for sample
  names/FOV ranges, writing a `samples.yaml`, and producing merged feature CSVs from
  `processing_results.yaml`.

## Features

### GUI Features

- **File Pickers**: Browse for ND2 files and directories instead of typing paths
- **Visual Channel Selection**: Radio buttons and checkboxes for channel configuration
- **Feature Checkboxes**: Easy selection of available features with visual feedback
- **Real-time Validation**: Immediate feedback on configuration validity
- **Progress Indicators**: Visual feedback during workflow execution
- **Configuration Summary**: Review all settings before execution

### Dynamic Feature Discovery

Both CLI and GUI automatically discover available features from the PyAMA core
library:

- **Phase contrast features**: `area`, `aspect_ratio` (and any custom features)
- **Fluorescence features**: `intensity_total` (and any custom features)

### Enhanced Configuration

- Time units configuration for output data
- Automatic feature validation and fallback to defaults
- Improved error handling and user feedback
- Sample management with FOV range validation

## Command Reference

```bash
# Show help for main commands
pyama-air --help

# Show help for CLI subcommands
pyama-air cli --help
pyama-air cli workflow --help
pyama-air cli merge --help

# Show help for GUI
pyama-air gui --help
```

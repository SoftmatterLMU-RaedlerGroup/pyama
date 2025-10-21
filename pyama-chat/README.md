# pyama-chat

`pyama-chat` provides conversational command-line helpers that guide you through
common PyAMA tasks without opening the Qt application.

## Commands

- `pyama-chat workflow` asks for an ND2 file, phase-contrast and fluorescence channel
  selections, feature options, time units, and batching parameters before kicking off
  the full processing workflow. Features are automatically discovered from the PyAMA
  core library.
- `pyama-chat merge` mirrors the merge panel from the Qt app, prompting for sample
  names/FOV ranges, writing a `samples.yaml`, and producing merged feature CSVs from
  `processing_results.yaml`.

## Features

### Dynamic Feature Discovery

The workflow command automatically discovers available features from the PyAMA core
library:

- **Phase contrast features**: `area`, `aspect_ratio` (and any custom features)
- **Fluorescence features**: `intensity_total` (and any custom features)

### Enhanced Configuration

- Time units configuration for output data
- Automatic feature validation and fallback to defaults
- Improved error handling and user feedback

Run `pyama-chat --help` for an overview or `pyama-chat <command> --help` for command
details.

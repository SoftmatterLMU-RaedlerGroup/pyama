# pyama-chat

`pyama-chat` provides conversational command-line helpers that guide you through
common PyAMA tasks without opening the Qt application.

## Commands

- `pyama-chat workflow` asks for an ND2 file, phase-contrast and fluorescence channel
  selections, and batching parameters before kicking off the full processing workflow.
- `pyama-chat merge` mirrors the merge panel from the Qt app, prompting for sample
  names/FOV ranges, writing a `samples.yaml`, and producing merged feature CSVs from
  `processing_results.yaml`.

Run `pyama-chat --help` for an overview or `pyama-chat <command> --help` for command
details.

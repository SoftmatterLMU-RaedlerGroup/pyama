#!/scratch-local/Tianyi.Cao/pyama/.venv/bin/python
"""
Generated from tests/test_workflow.ipynb
This script mirrors the notebook's code cells so you can run the workflow from the CLI.
Update microscopy_path and OUTPUT_DIR as needed before running.
"""

from pathlib import Path
import logging

from pyama_core.io import load_microscopy_file
from pyama_core.processing.workflow.pipeline import run_complete_workflow
from pyama_core.processing.workflow.services.types import Channels, ProcessingContext


def main() -> None:
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    print("Starting workflow test...")

    # Configure inputs
    microscopy_path = Path("/mnt/crucial/250129_HuH7/250129_HuH7.nd2")
    OUTPUT_DIR = Path("/mnt/crucial/250129_HuH7")

    print(f"Microscopy path: {microscopy_path}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Select channels by index
    PC_CH = 0
    FL_CHS = [1, 2]  # list of ints (test multi-fluorescence)

    # Build per-channel feature mapping using dedicated discovery helpers
    from pyama_core.processing.extraction.feature import (
        list_fluorescence_features,
        list_phase_features,
    )

    fl_feature_choices = list_fluorescence_features()
    fl_features = {ch: fl_feature_choices for ch in FL_CHS}
    pc_features = list_phase_features()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print("Created output directory")

    # Load metadata (for verification) and build context
    print("Loading microscopy file...")
    _img, md = load_microscopy_file(microscopy_path)
    print("Loaded microscopy file successfully")
    # pprint(md)

    # Build context using current schema (see pyama_core.workflow.services.types)
    ctx = ProcessingContext(
        output_dir=OUTPUT_DIR,
        channels=Channels.from_feature_mapping(
            pc_channel=PC_CH,
            pc_features=pc_features,
            fl_features=fl_features,
        ),
        params={},
    )
    print(ctx)

    # Run the workflow
    print("Starting workflow execution...")
    success = run_complete_workflow(
        metadata=md,
        context=ctx,
        fov_start=0,
        fov_end=1,
        batch_size=2,
        n_workers=2,
    )
    print("Success:", success)

    # Show final context
    print(ctx)


if __name__ == "__main__":
    main()

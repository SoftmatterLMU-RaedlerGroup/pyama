"""
Generated from tests/test_workflow.ipynb
This script mirrors the notebook's code cells so you can run the workflow from the CLI.
Update ND2_PATH and OUTPUT_DIR as needed before running.
"""
from pathlib import Path
import logging
from pprint import pprint

from pyama_core.io import load_nd2
from pyama_core.workflow.pipeline import run_complete_workflow
from pyama_core.workflow.services.types import ProcessingContext


def main() -> None:
    # Configure logging
    logging.basicConfig(level=logging.INFO)

    # Configure inputs
    ND2_PATH = Path("E:/250129_HuH7/250129_HuH7.nd2")  # change me
    OUTPUT_DIR = Path("E:/250129_HuH7")

    # Select channels by index
    PC_CH = 0
    FL_CHS = [1, 2]  # list of ints (test multi-fluorescence)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load metadata (for verification) and build context
    _, md = load_nd2(ND2_PATH)
    # pprint(md)

    # Build context using current schema (see pyama_core.workflow.services.types)
    ctx: ProcessingContext = {
        "output_dir": OUTPUT_DIR,
        "channels": {
            "pc": PC_CH,
            "fl": FL_CHS,
        },
        "npy_paths": {},
        "params": {},
    }

    # Run the workflow
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
    pprint(ctx)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Entry point for python -m pyama_qt

Supports both processing and visualization modes:
- python -m pyama_qt process   -> Launch processing GUI
- python -m pyama_qt viz       -> Launch visualization GUI
"""

import sys
import multiprocessing as mp

def main():
    """Main entry point with mode selection."""
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "viz" or mode == "visualize":
            from pyama_qt.visualization.main import main as viz_main
            # Remove the mode argument before launching
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            viz_main()
        elif mode == "process" or mode == "processing":
            from pyama_qt.processing.main import main as proc_main
            # Remove the mode argument before launching
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            proc_main()
        else:
            print(f"Error: Unknown mode '{sys.argv[1]}'")
            print()
            print("Usage: python -m pyama_qt <mode>")
            print()
            print("Available modes:")
            print("  process  Launch processing application")
            print("  viz      Launch visualization application")
            sys.exit(1)
    else:
        # No argument provided - show usage and exit
        print("Error: No mode specified")
        print()
        print("Usage: python -m pyama_qt <mode>")
        print()
        print("Available modes:")
        print("  process  Launch processing application")
        print("  viz      Launch visualization application")
        sys.exit(1)

if __name__ == "__main__":
    # These calls are essential for bundled applications on macOS.
    # freeze_support() must be the first call.
    # 'spawn' is the most robust start method for frozen executables.
    mp.freeze_support()
    mp.set_start_method("spawn", True)
    main()
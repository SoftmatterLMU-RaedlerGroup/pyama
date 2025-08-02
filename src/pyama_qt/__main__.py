#!/usr/bin/env python3
"""
Entry point for python -m pyama_qt

Supports both processing and visualization modes:
- python -m pyama_qt process   -> Launch processing GUI
- python -m pyama_qt viz       -> Launch visualization GUI
"""

import sys

def main():
    """Main entry point with mode selection."""
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
        if mode == "viz" or mode == "visualize":
            from .visualization.main import main as viz_main
            # Remove the mode argument before launching
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            viz_main()
        elif mode == "process" or mode == "processing":
            from .processing.main import main as proc_main
            # Remove the mode argument before launching
            sys.argv = [sys.argv[0]] + sys.argv[2:]
            proc_main()
        else:
            print("Usage: python -m pyama_qt [process|viz]")
            print("  process: Launch processing application")
            print("  viz:     Launch visualization application")
            sys.exit(1)
    else:
        print("Usage: python -m pyama_qt [process|viz]")
        print("  process: Launch processing application")
        print("  viz:     Launch visualization application")
        sys.exit(1)

if __name__ == "__main__":
    main()
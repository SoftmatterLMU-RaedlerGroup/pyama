#!/usr/bin/env python
"""
Quick NPY viewer for PyAMA-Qt test outputs.

Usage:
    python view_npy.py <npy_file>
    python view_npy.py <directory>  # Shows all NPY files in directory
    python view_npy.py  # Interactive mode
"""

import sys
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
from typing import Optional
import random

def visualize_npy(npy_path: Path, frame: Optional[int] = None) -> None:
    """Visualize NPY file contents."""
    print(f"\nLoading: {npy_path}")
    
    try:
        # Load as memory-mapped array to handle large files efficiently
        array = np.load(npy_path, mmap_mode='r')
        
        print(f"Shape: {array.shape}, dtype: {array.dtype}")
        
        if array.ndim == 3:  # Time series data
            n_frames, height, width = array.shape
            print(f"Time series with {n_frames} frames, {height}x{width} pixels")
            
            # Select frame to display
            if frame is None:
                display_frame = random.randint(0, n_frames - 1)  # Random frame by default
            else:
                display_frame = min(frame, n_frames - 1)
            
            # Create figure
            fig, ax = plt.subplots(1, 1, figsize=(8, 8))
            
            # Display image based on data type and filename
            if 'binarized' in npy_path.name or array.dtype == np.bool_:
                # Binary data - show in black and white
                im = ax.imshow(array[display_frame], cmap='gray', vmin=0, vmax=1)
                ax.set_title(f"{npy_path.name}\nFrame {display_frame}/{n_frames-1}")
            else:
                # Continuous data - show with colormap
                im = ax.imshow(array[display_frame], cmap='viridis')
                ax.set_title(f"{npy_path.name}\nFrame {display_frame}/{n_frames-1}")
                plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
            
            ax.axis('off')
            
        elif array.ndim == 2:  # Single image
            fig, ax = plt.subplots(1, 1, figsize=(8, 8))
            
            if 'binarized' in npy_path.name or array.dtype == np.bool_:
                im = ax.imshow(array, cmap='gray', vmin=0, vmax=1)
            else:
                im = ax.imshow(array, cmap='viridis')
                plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
                
            ax.set_title(f"{npy_path.name}")
            ax.axis('off')
            
        else:
            print(f"Unsupported array dimensions: {array.ndim}D")
            return
            
        plt.tight_layout()
        plt.show()
        
    except Exception as e:
        print(f"Error loading {npy_path}: {e}")

def list_npy_files(directory: Path) -> list[Path]:
    """List all NPY files in a directory recursively."""
    return sorted(directory.rglob("*.npy"))

def interactive_mode(directory: Path) -> None:
    """Interactive mode to browse and view NPY files."""
    npy_files = list_npy_files(directory)
    
    if not npy_files:
        print(f"No NPY files found in {directory}")
        return
        
    print(f"\nFound {len(npy_files)} NPY files:")
    for i, f in enumerate(npy_files):
        # Show relative path for readability
        rel_path = f.relative_to(directory) if f.is_relative_to(directory) else f
        print(f"{i:3d}: {rel_path}")
    
    while True:
        try:
            choice = input("\nEnter file number to view (q to quit): ").strip()
            if choice.lower() == 'q':
                break
                
            idx = int(choice)
            if 0 <= idx < len(npy_files):
                # Quick check of file info
                array = np.load(npy_files[idx], mmap_mode='r')
                if array.ndim == 3:
                    frame_input = input(f"Frame number (0-{array.shape[0]-1}, Enter for random): ").strip()
                    frame = int(frame_input) if frame_input else None
                else:
                    frame = None
                visualize_npy(npy_files[idx], frame)
            else:
                print(f"Invalid index. Please enter 0-{len(npy_files)-1}")
                
        except ValueError:
            print("Invalid input. Please enter a number or 'q'")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

def main():
    parser = argparse.ArgumentParser(description="View NPY files from PyAMA-Qt tests")
    parser.add_argument("path", nargs="?", help="NPY file or directory path")
    parser.add_argument("-f", "--frame", type=int, help="Frame number to display (for time series)")
    
    args = parser.parse_args()
    
    if args.path:
        path = Path(args.path)
        
        if path.is_file() and path.suffix == '.npy':
            # Single file mode
            visualize_npy(path, args.frame)
        elif path.is_dir():
            # Directory mode - interactive browser
            interactive_mode(path)
        else:
            print(f"Error: {path} is not a valid NPY file or directory")
            return 1
    else:
        # No path provided - use current directory
        interactive_mode(Path.cwd())
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
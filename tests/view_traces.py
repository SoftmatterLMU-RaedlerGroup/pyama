#!/usr/bin/env python
"""
Quick trace CSV viewer for PyAMA-Qt test outputs.

Usage:
    python view_traces.py <csv_file>
    python view_traces.py <directory>  # Shows all trace CSV files in directory
    python view_traces.py  # Interactive mode
"""

import sys
import pandas as pd
import matplotlib.pyplot as plt
from pathlib import Path
import argparse
import numpy as np

def visualize_traces(csv_path: Path, cell_ids: list[int] | None = None, max_cells: int = 10) -> None:
    """Visualize trace CSV file contents."""
    print(f"\nLoading: {csv_path}")
    
    try:
        # Load CSV data
        df = pd.read_csv(csv_path)
        
        print(f"Shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Get unique cell IDs
        if 'cell_id' not in df.columns:
            print("No 'cell_id' column found in trace data")
            return
        
        cell_id_col = 'cell_id'
            
        unique_cells = df[cell_id_col].unique()
        n_cells = len(unique_cells)
        print(f"Unique cells: {n_cells}")
        
        if n_cells == 0:
            print("No cells found in trace data")
            return
        
        # Select cells to display
        if cell_ids is None:
            # Show first few cells or random selection if too many
            if n_cells <= max_cells:
                display_cells = unique_cells
            else:
                # Random selection
                display_cells = np.random.choice(unique_cells, max_cells, replace=False)
                print(f"Randomly selected {max_cells} cells to display")
        else:
            # Filter to requested cell IDs that exist
            display_cells = [cid for cid in cell_ids if cid in unique_cells]
            if not display_cells:
                print(f"None of the requested cell IDs {cell_ids} found in data")
                return
        
        # Create subplots based on available data
        n_plots = 0
        intensity_cols = ['intensity_total', 'fl_int_mean', 'mean_intensity']
        if any(col in df.columns for col in intensity_cols):
            n_plots += 1
        if 'area' in df.columns:
            n_plots += 1
        if 'eccentricity' in df.columns:
            n_plots += 1
        
        if n_plots == 0:
            print("No plottable columns found (fl_int_mean, area, eccentricity)")
            return
        
        fig, axes = plt.subplots(n_plots, 1, figsize=(12, 4 * n_plots), sharex=True)
        if n_plots == 1:
            axes = [axes]
        
        # Plot each cell's traces
        colors = plt.cm.tab10(np.linspace(0, 1, len(display_cells)))
        
        for i, cell_id in enumerate(display_cells):
            cell_data = df[df['cell_id'] == cell_id].sort_values('frame')
            
            plot_idx = 0
            
            # Use frame column for time
            time_col = 'frame'
            
            # Plot fluorescence intensity
            intensity_cols = ['intensity_total', 'fl_int_mean', 'mean_intensity']
            intensity_col = None
            for col in intensity_cols:
                if col in df.columns:
                    intensity_col = col
                    break
                    
            if intensity_col:
                axes[plot_idx].plot(cell_data[time_col], cell_data[intensity_col], 
                                  color=colors[i], label=f'Cell {cell_id}', alpha=0.8, linewidth=2)
                if i == 0:
                    axes[plot_idx].set_ylabel('Fluorescence Intensity')
                    axes[plot_idx].set_title(f'{csv_path.name} - Fluorescence Traces')
                    axes[plot_idx].grid(True, alpha=0.3)
                plot_idx += 1
            
            # Plot area
            if 'area' in df.columns:
                axes[plot_idx].plot(cell_data[time_col], cell_data['area'], 
                                  color=colors[i], label=f'Cell {cell_id}', alpha=0.8, linewidth=2)
                if i == 0:
                    axes[plot_idx].set_ylabel('Area (pixels)')
                    axes[plot_idx].set_title('Cell Area Over Time')
                    axes[plot_idx].grid(True, alpha=0.3)
                plot_idx += 1
            
            # Plot eccentricity
            if 'eccentricity' in df.columns:
                axes[plot_idx].plot(cell_data[time_col], cell_data['eccentricity'], 
                                  color=colors[i], label=f'Cell {cell_id}', alpha=0.8, linewidth=2)
                if i == 0:
                    axes[plot_idx].set_ylabel('Eccentricity')
                    axes[plot_idx].set_title('Cell Shape (Eccentricity) Over Time')
                    axes[plot_idx].grid(True, alpha=0.3)
                plot_idx += 1
        
        # Set x-label on bottom plot
        axes[-1].set_xlabel('Time (frames)')
        
        # Add legend to first plot
        if len(display_cells) <= 15:  # Only show legend if not too many cells
            axes[0].legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        
        plt.tight_layout()
        plt.show()
        
        # Print summary statistics
        print("\nSummary statistics:")
        
        # Find intensity column
        intensity_col = None
        for col in intensity_cols:
            if col in df.columns:
                intensity_col = col
                break
        
        if intensity_col:
            print(f"  Fluorescence range: {df[intensity_col].min():.2f} - {df[intensity_col].max():.2f}")
        if 'area' in df.columns:
            print(f"  Area range: {df['area'].min():.0f} - {df['area'].max():.0f} pixels")
        if 'eccentricity' in df.columns:
            print(f"  Eccentricity range: {df['eccentricity'].min():.3f} - {df['eccentricity'].max():.3f}")
        
        print(f"  Frame range: {df['frame'].min()} - {df['frame'].max()}")
        
    except Exception as e:
        print(f"Error loading {csv_path}: {e}")

def list_trace_files(directory: Path) -> list[Path]:
    """List all trace CSV files in a directory recursively."""
    return sorted(directory.rglob("*traces.csv"))

def interactive_mode(directory: Path) -> None:
    """Interactive mode to browse and view trace CSV files."""
    csv_files = list_trace_files(directory)
    
    if not csv_files:
        print(f"No trace CSV files found in {directory}")
        return
        
    print(f"\nFound {len(csv_files)} trace CSV files:")
    for i, f in enumerate(csv_files):
        # Show relative path for readability
        rel_path = f.relative_to(directory) if f.is_relative_to(directory) else f
        print(f"{i:3d}: {rel_path}")
    
    while True:
        try:
            choice = input("\nEnter file number to view (q to quit): ").strip()
            if choice.lower() == 'q':
                break
                
            idx = int(choice)
            if 0 <= idx < len(csv_files):
                # Quick check of file info
                df = pd.read_csv(csv_files[idx])
                # Check for cell_id column
                if 'cell_id' not in df.columns:
                    print("No 'cell_id' column found")
                    continue
                n_cells = df['cell_id'].nunique()
                
                cell_input = input(f"Cell IDs to plot (comma-separated, Enter for auto-select up to 10): ").strip()
                if cell_input:
                    try:
                        cell_ids = [int(x.strip()) for x in cell_input.split(',')]
                    except ValueError:
                        print("Invalid cell ID format. Using auto-selection.")
                        cell_ids = None
                else:
                    cell_ids = None
                    
                visualize_traces(csv_files[idx], cell_ids)
            else:
                print(f"Invalid index. Please enter 0-{len(csv_files)-1}")
                
        except ValueError:
            print("Invalid input. Please enter a number or 'q'")
        except KeyboardInterrupt:
            print("\nExiting...")
            break

def main():
    parser = argparse.ArgumentParser(description="View trace CSV files from PyAMA-Qt tests")
    parser.add_argument("path", nargs="?", help="CSV file or directory path")
    parser.add_argument("-c", "--cells", type=str, help="Comma-separated list of cell IDs to plot")
    parser.add_argument("-m", "--max-cells", type=int, default=10, help="Maximum number of cells to display (default: 10)")
    
    args = parser.parse_args()
    
    # Parse cell IDs if provided
    cell_ids = None
    if args.cells:
        try:
            cell_ids = [int(x.strip()) for x in args.cells.split(',')]
        except ValueError:
            print("Error: Invalid cell ID format. Use comma-separated integers.")
            return 1
    
    if args.path:
        path = Path(args.path)
        
        if path.is_file() and path.suffix == '.csv':
            # Single file mode
            visualize_traces(path, cell_ids, args.max_cells)
        elif path.is_dir():
            # Directory mode - interactive browser
            interactive_mode(path)
        else:
            print(f"Error: {path} is not a valid CSV file or directory")
            return 1
    else:
        # No path provided - use current directory
        interactive_mode(Path.cwd())
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
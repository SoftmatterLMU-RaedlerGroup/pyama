#!/usr/bin/env python3
"""Test fitting with TrivialModel using real data from HuH7_FCSnew_GFP.csv."""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import sys
import os
from pathlib import Path

# Add the src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from pyama_qt.analysis.models.trivial import TrivialModel
from pyama_qt.analysis.utils.fitting import fit_model

def load_and_transform_data(csv_path: str, n_cells: int = 10):
    """
    Load data from CSV and transform to required format.
    
    CSV format:
    - First row: column indices (ignored)
    - First column: time in hours
    - Remaining columns: one cell per column
    """
    # Read CSV, skip the first row (column indices)
    df = pd.read_csv(csv_path, skiprows=1, header=None)
    
    # First column is time in hours
    time_hours = df.iloc[:, 0].values
    
    # Get data for first n_cells (columns 1 to n_cells+1)
    cells_data = []
    for cell_id in range(1, min(n_cells + 1, df.shape[1])):
        intensity = df.iloc[:, cell_id].values
        cells_data.append({
            'cell_id': cell_id,
            'time': time_hours,
            'intensity': intensity
        })
    
    return cells_data

def plot_fit_results(cell_data, fit_result, model, cell_id, output_dir):
    """Plot data points and fitted curve for a single cell."""
    
    # Create output directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    # Extract time and intensity
    t_data = cell_data['time']
    y_data = cell_data['intensity']
    
    # Remove NaN values for plotting
    mask = ~(np.isnan(t_data) | np.isnan(y_data))
    t_clean = t_data[mask]
    y_clean = y_data[mask]
    
    # Generate fitted curve
    if fit_result.success and fit_result.fitted_params:
        # Create fine time grid for smooth curve
        t_fit = np.linspace(t_clean.min(), t_clean.max(), 500)
        
        # Evaluate model with fitted parameters
        y_fit = model.eval(
            t_fit,
            t0=fit_result.fitted_params.get('t0', 0),
            ktl=fit_result.fitted_params.get('ktl', 0),
            delta=fit_result.fitted_params.get('delta', 0),
            beta=fit_result.fitted_params.get('beta', 0),
            offset=fit_result.fitted_params.get('offset', 0)
        )
    else:
        t_fit = None
        y_fit = None
    
    # Create figure
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot data points
    ax.scatter(t_clean, y_clean, alpha=0.5, s=10, label='Data', color='blue')
    
    # Plot fitted curve if available
    if t_fit is not None and y_fit is not None:
        ax.plot(t_fit, y_fit, 'r-', linewidth=2, label='Fitted curve')
    
    # Add labels and title
    ax.set_xlabel('Time (hours)', fontsize=12)
    ax.set_ylabel('Intensity', fontsize=12)
    ax.set_title(f'Cell {cell_id} - Trivial Model Fit\nχ² = {fit_result.chisq:.2e}', fontsize=14)
    ax.legend()
    ax.grid(True, alpha=0.3)
    
    # Add parameter text box
    if fit_result.success:
        param_text = '\n'.join([
            f"Parameters:",
            f"t0 = {fit_result.fitted_params.get('t0', 0):.3f}",
            f"ktl = {fit_result.fitted_params.get('ktl', 0):.3f}",
            f"delta = {fit_result.fitted_params.get('delta', 0):.6f}",
            f"beta = {fit_result.fitted_params.get('beta', 0):.6f}",
            f"offset = {fit_result.fitted_params.get('offset', 0):.3f}"
        ])
        ax.text(0.02, 0.98, param_text, transform=ax.transAxes,
                fontsize=10, verticalalignment='top',
                bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
    
    # Save figure
    output_path = os.path.join(output_dir, f'cell_{cell_id:03d}_fit.png')
    plt.savefig(output_path, dpi=100, bbox_inches='tight')
    plt.close()
    
    print(f"  Saved plot to {output_path}")

def test_fitting_with_real_data():
    """Test fitting using real data from HuH7_FCSnew_GFP.csv."""
    
    # Path to data file
    data_file = 'data/HuH7_FCSnew_GFP.csv'
    output_dir = 'test_results'
    
    print(f"Loading data from {data_file}...")
    
    # Load data for 10 cells
    cells_data = load_and_transform_data(data_file, n_cells=10)
    
    print(f"Loaded data for {len(cells_data)} cells")
    print(f"Time points: {len(cells_data[0]['time'])}")
    print()
    
    # Process each cell
    for cell_data in cells_data:
        cell_id = cell_data['cell_id']
        print(f"=== Cell {cell_id} ===")
        
        # Create TrivialModel with empty parameters (as required)
        model = TrivialModel({})
        
        # Perform fitting
        fit_result = fit_model(
            model,
            cell_data['time'],
            cell_data['intensity']
        )
        
        # Print results
        print(f"  Success: {fit_result.success}")
        print(f"  Chi-squared: {fit_result.chisq:.2e}")
        
        if fit_result.success:
            print("  Fitted parameters:")
            for name, value in fit_result.fitted_params.items():
                print(f"    {name}: {value:.6f}")
        else:
            print(f"  Error: {fit_result.message}")
        
        # Plot results
        plot_fit_results(cell_data, fit_result, model, cell_id, output_dir)
        
        print()
    
    print(f"\nAll plots saved to {output_dir}/")

if __name__ == "__main__":
    test_fitting_with_real_data()
# PyAMA-Qt (UI-Only Implementation)

This is a UI-only implementation of the PyAMA-Qt application, providing the graphical user interface components without business logic or model/controller implementations.

## Features

- **Processing Tab**: Workflow management and result merging
- **Analysis Tab**: Data loading, model fitting, and results display
- **Visualization Tab**: Image viewing, project management, and trace analysis

## Installation

```bash
# Using uv (recommended)
uv add pyama-qt

# Or using pip
pip install pyama-qt
```

## Usage

```bash
# Run the application
pyama-qt

# Or using uv
uv run pyama-qt
```

## Development

This is a UI-only implementation that serves as a starting point for integrating with business logic models and controllers.

### Project Structure

- `src/pyama_qt/ui/`: Base UI classes and common widgets
- `src/pyama_qt/pages/`: Main application pages (Processing, Analysis, Visualization)
- `src/pyama_qt/panels/`: Individual panel components within pages
- `src/pyama_qt/components/`: Reusable UI components (MplCanvas, etc.)

## Dependencies

- PySide6: Qt Python bindings
- matplotlib: Plotting library
- numpy: Numerical computations
- pyama-core: Core PyAMA functionality

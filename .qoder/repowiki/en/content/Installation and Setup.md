# Installation and Setup

<cite>
**Referenced Files in This Document**   
- [pyproject.toml](file://pyama-core/pyproject.toml)
- [pyproject.toml](file://pyama-qt/pyproject.toml)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml)
- [main.py](file://pyama-qt/src/pyama_qt/main.py)
- [config.yaml](file://pyama-qt/src/pyama_qt/config.yaml)
</cite>

## Table of Contents
1. [Python Version Requirements](#python-version-requirements)
2. [Core Components Overview](#core-components-overview)
3. [Installation Methods](#installation-methods)
4. [Virtual Environment Setup](#virtual-environment-setup)
5. [Platform-Specific Considerations](#platform-specific-considerations)
6. [Workspace Configuration](#workspace-configuration)
7. [Qt Application Variants](#qt-application-variants)
8. [Troubleshooting Common Issues](#troubleshooting-common-issues)

## Python Version Requirements

PyAMA requires Python 3.11 or higher for all components. The project leverages modern Python features and type hints that are not available in earlier versions. Users should verify their Python version using:

```bash
python --version
```

The minimum required version is specified in all component pyproject.toml files with `requires-python = ">=3.11"`. This ensures compatibility with the latest scientific computing libraries and proper handling of type annotations used throughout the codebase.

**Section sources**
- [pyproject.toml](file://pyama-core/pyproject.toml#L8)
- [pyproject.toml](file://pyama-qt/pyproject.toml#L8)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml#L8)

## Core Components Overview

PyAMA consists of three main components with a clear dependency hierarchy:

- **pyama-core**: The foundational processing library containing all algorithmic implementations for microscopy data analysis, including image processing, segmentation, tracking, and analysis workflows.
- **pyama-qt**: A full-featured Qt-based graphical user interface that provides complete functionality for processing, analysis, and visualization of microscopy data.
- **pyama-qt-slim**: A UI-only implementation of the PyAMA-Qt application that provides the graphical interface components without business logic, intended as a starting point for integration with custom models and controllers.

The core library is designed to be used programmatically, while the Qt applications provide interactive interfaces for users who prefer a GUI approach.

**Section sources**
- [pyproject.toml](file://pyama-core/pyproject.toml#L4)
- [pyproject.toml](file://pyama-qt/pyproject.toml#L4)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml#L4)

## Installation Methods

### Using pip

All PyAMA components can be installed via pip, the Python package installer. For the complete suite:

```bash
pip install pyama-core pyama-qt
```

For users who only need the core processing functionality:

```bash
pip install pyama-core
```

The slim Qt interface can be installed separately:

```bash
pip install pyama-qt-slim
```

### Using Poetry

For projects already using Poetry as their dependency manager, add PyAMA components to your pyproject.toml:

```toml
[tool.poetry.dependencies]
pyama-core = "^0.1.0"
pyama-qt = "^0.1.0"
```

Then install with:

```bash
poetry install
```

### Using uv (Recommended)

For optimal dependency resolution and installation speed, use the uv package manager:

```bash
# Install all components
uv add pyama-core pyama-qt

# Install only core functionality
uv add pyama-core
```

uv provides faster installation and more reliable dependency resolution compared to pip, especially for scientific Python packages with complex dependency trees.

**Section sources**
- [pyproject.toml](file://pyama-core/pyproject.toml#L1-L26)
- [pyproject.toml](file://pyama-qt/pyproject.toml#L1-L28)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml#L1-L27)

## Virtual Environment Setup

It is strongly recommended to use virtual environments when installing PyAMA to avoid dependency conflicts with other Python projects.

### Creating a Virtual Environment

```bash
# Create a new virtual environment
python -m venv pyama-env

# Activate the environment
# On Windows:
pyama-env\Scripts\activate
# On macOS/Linux:
source pyama-env/bin/activate
```

### Installing with Virtual Environment

```bash
# Activate your environment first
source pyama-env/bin/activate  # or pyama-env\Scripts\activate on Windows

# Upgrade pip to latest version
pip install --upgrade pip

# Install PyAMA components
pip install pyama-core pyama-qt
```

### Using Poetry with Virtual Environments

Poetry automatically manages virtual environments:

```bash
# Initialize a new poetry project
poetry init

# Add PyAMA dependencies
poetry add pyama-core pyama-qt

# Poetry automatically creates and manages the virtual environment
```

**Section sources**
- [pyproject.toml](file://pyama-core/pyproject.toml#L1-L26)
- [pyproject.toml](file://pyama-qt/pyproject.toml#L1-L28)

## Platform-Specific Considerations

### Windows

On Windows systems, ensure that the Microsoft Visual C++ Redistributable packages are installed, as they are required by many scientific Python packages. The multiprocessing setup in pyama-qt includes Windows-specific code (`mp.freeze_support()`) to ensure proper operation.

When installing PySide6, users may encounter issues with missing DLLs. If this occurs, try:

```bash
pip install --force-reinstall --no-cache-dir pyside6
```

### macOS

On macOS, ensure Xcode command line tools are installed:

```bash
xcode-select --install
```

Some users may need to install additional libraries via Homebrew:

```bash
brew install libomp
```

### Linux

On Linux distributions, install system-level dependencies before installing PyAMA:

```bash
# Ubuntu/Debian
sudo apt-get install python3-dev libomp-dev

# CentOS/RHEL
sudo yum install python3-devel libomp-devel
```

The Qt backend may require additional X11 libraries on headless servers or when using remote desktop connections.

**Section sources**
- [main.py](file://pyama-qt/src/pyama_qt/main.py#L7-L15)

## Workspace Configuration

### Environment Variables

PyAMA does not require specific environment variables to function, but users can customize behavior through configuration files. The application looks for configuration in the same directory as the executable.

### Directory Structure

The recommended workspace structure for PyAMA projects:

```
project-root/
├── data/               # Raw microscopy data (ND2, CZI, etc.)
├── processed/          # Processed results and CSV outputs
├── analysis/           # Analysis results and fitted models
├── config/             # Configuration files
└── notebooks/          # Jupyter notebooks for exploration
```

### Configuration File

The pyama-qt application includes a config.yaml file that can be customized:

```yaml
# Default directory for file dialogs
# Users can customize this path to their preferred location
# DEFAULT_DIR: "/project/ag-moonraedler"
```

To set a custom default directory, uncomment and modify the DEFAULT_DIR line with your preferred path.

**Section sources**
- [config.yaml](file://pyama-qt/src/pyama_qt/config.yaml#L1-L7)
- [main.py](file://pyama-qt/src/pyama_qt/main.py#L20-L25)

## Qt Application Variants

### pyama-qt (Full Application)

The full pyama-qt application provides complete functionality with business logic, models, and controllers implemented. It includes:

- Processing tab: Workflow management and result merging
- Analysis tab: Data loading, model fitting, and results display
- Visualization tab: Image viewing, project management, and trace analysis

The application is launched via the entry point defined in pyproject.toml: `pyama-qt = "pyama_qt.main:main"`.

### pyama-qt-slim (UI-Only)

The slim variant provides only the graphical interface components without business logic. It serves as a starting point for integrating with custom models and controllers. This version is useful for:

- Developers building custom analysis pipelines
- Organizations that want to maintain their own business logic
- Educational purposes and code examples

Both variants share the same dependencies and installation process, but the full application contains the complete implementation while the slim version provides only the UI framework.

**Section sources**
- [pyproject.toml](file://pyama-qt/pyproject.toml#L4)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml#L4)
- [main.py](file://pyama-qt/src/pyama_qt/main.py#L1-L74)
- [README.md](file://pyama-qt-slim/README.md#L1-L47)

## Troubleshooting Common Issues

### Missing DLLs on Windows

If you encounter missing DLL errors when launching pyama-qt:

1. Try reinstalling PySide6:
```bash
pip uninstall pyside6 && pip install pyside6
```

2. Ensure you have the latest Microsoft Visual C++ Redistributable installed.

3. Run the application from the command line to see detailed error messages.

### Qt Backend Conflicts

When multiple Qt bindings are installed (PySide6, PyQt5, PyQt6), conflicts can occur:

```bash
# Uninstall other Qt bindings
pip uninstall pyqt5 pyqt6

# Reinstall PySide6
pip install pyside6
```

### bioio Plugin Errors

The pyama-core package depends on bioio and its format-specific plugins (bioio-nd2, bioio-czi). If you encounter errors reading microscopy files:

1. Verify all bioio packages are installed:
```bash
pip install bioio bioio-nd2 bioio-czi
```

2. Check that your file format is supported by the installed plugins.

3. Ensure file permissions allow reading.

### Dependency Resolution Issues

For complex dependency conflicts, use uv for more reliable resolution:

```bash
# Clear pip cache
pip cache purge

# Use uv for installation
uv pip install pyama-core pyama-qt
```

### Virtual Environment Problems

If the application cannot find installed packages:

1. Verify the virtual environment is activated.
2. Check that you're using the correct Python interpreter.
3. Reinstall packages within the activated environment.

**Section sources**
- [pyproject.toml](file://pyama-core/pyproject.toml#L10-L18)
- [pyproject.toml](file://pyama-qt/pyproject.toml#L10-L16)
- [pyproject.toml](file://pyama-qt-slim/pyproject.toml#L10-L16)
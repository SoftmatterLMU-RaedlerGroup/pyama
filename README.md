# PyAMA

PyAMA is a modular Python application for analysis. It consists of a core library, a Qt-based graphical user interface, and a FastAPI-based web service.

## Packages

This repository is a workspace containing the following packages:

*   `pyama-core`: Core processing library for PyAMA.
*   `pyama-qt`: Qt-based GUI for PyAMA. This package provides the following commands:
    *   `pyama-process`: Opens the processing window.
    *   `pyama-viz`: Opens the visualization window.
    *   `pyama-analysis`: Opens the analysis window.
*   `pyama-fastapi`: FastAPI service for PyAMA processing. This package provides the following command:
    *   `pyama-api`: Starts the FastAPI server.

## Project Structure

```
pyama/
├── pyama-core/
│   └── pyama_core/
│       ├── analysis/
│       ├── core/
│       ├── processing/
│       ├── utils/
│       └── visualization/
├── pyama-fastapi/
│   └── pyama_fastapi/
│       ├── main.py
│       └── services/
└── pyama-qt/
    └── pyama_qt/
        ├── analysis/
        ├── core/
        ├── processing/
        ├── utils/
        └── visualization/
```
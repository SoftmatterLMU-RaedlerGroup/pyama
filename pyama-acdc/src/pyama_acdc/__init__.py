"""PyAMA ↔ Cell-ACDC integration helpers."""

from __future__ import annotations

import os

pyama_acdc_path = os.path.dirname(os.path.abspath(__file__))
resources_folderpath = os.path.join(pyama_acdc_path, "resources")
icon_path = os.path.join(resources_folderpath, "pyama_icon.svg")
logo_path = os.path.join(resources_folderpath, "pyama_logo.svg")

from .gui import pyAMA_Win, PyamaCustomPreprocessDialog, PyamaPlaceholderDialog

__all__ = [
    "pyAMA_Win",
    "PyamaCustomPreprocessDialog",
    "PyamaPlaceholderDialog",
    "pyama_acdc_path",
    "resources_folderpath",
    "icon_path",
    "logo_path",
]

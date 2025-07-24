"""
PyAMA-Qt Processing Application

Microscopy image analysis pipeline for phase contrast and fluorescence data.
Performs binarization, background correction, and trace extraction.
"""

from .main import main

__all__ = ["main"]
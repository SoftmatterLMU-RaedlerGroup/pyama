'''
Utility for copying channels from ND2 files into NPY files with progress reporting.

This module is a wrapper around the implementation in pyama_core.
'''

from pyama_core.processing.copy import (
    copy_channels_to_npy,
)

__all__ = [
    "copy_channels_to_npy",
]
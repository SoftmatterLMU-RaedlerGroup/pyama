"""Schema definitions for processing CSV rows."""

from __future__ import annotations

from typing import TypedDict

from pyama_core.processing.extraction.trace import Result, ResultIndex


class ProcessingCSVRow(TypedDict, total=False):
    """Row structure for processing CSV files with dynamic feature columns."""

    __annotations__ = {
        "fov": int,
        **ResultIndex.__annotations__,
        **Result.__annotations__,
    }


__all__ = ["ProcessingCSVRow"]

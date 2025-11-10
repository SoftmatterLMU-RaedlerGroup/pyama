"""Trace file discovery and selection helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Tuple

logger = logging.getLogger(__name__)


def select_trace_csv_file(
    csv_path: Path, *, context: str | None = None
) -> Tuple[Path | None, Path, Path]:
    """Select preferred trace CSV file, favoring inspected versions when available.

    Args:
        csv_path: Base or inspected CSV path reference
        context: Optional context string to prefix log messages with

    Returns:
        Tuple of (preferred_path_or_none, base_path, inspected_path)
    """
    candidate = Path(csv_path)
    if candidate.stem.endswith("_inspected"):
        base_stem = candidate.stem[: -len("_inspected")]
        base_path = candidate.with_name(f"{base_stem}{candidate.suffix}")
        inspected_path = candidate
    else:
        base_path = candidate
        inspected_path = candidate.with_name(
            f"{candidate.stem}_inspected{candidate.suffix}"
        )

    base_exists = base_path.exists()
    inspected_exists = inspected_path.exists()
    context_prefix = f"{context}: " if context else ""

    if inspected_exists:
        if base_exists:
            logger.debug(
                "%sFound %s and %s; using %s",
                context_prefix,
                base_path.name,
                inspected_path.name,
                inspected_path.name,
            )
        else:
            logger.debug(
                "%sFound %s; using %s",
                context_prefix,
                inspected_path.name,
                inspected_path.name,
            )
        return inspected_path, base_path, inspected_path

    if base_exists:
        logger.debug(
            "%sFound %s; using %s",
            context_prefix,
            base_path.name,
            base_path.name,
        )
        return base_path, base_path, inspected_path

    logger.warning(
        "%sNo trace CSV found (checked %s and %s)",
        context_prefix,
        base_path,
        inspected_path,
    )
    return None, base_path, inspected_path

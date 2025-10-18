"""Helpers for parsing and loading sample configurations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

import yaml


def parse_fov_range(text: str) -> List[int]:
    """Parse comma-separated FOV ranges (e.g., '0-5, 7, 9-11')."""
    normalized = text.replace(" ", "").strip()
    if not normalized:
        raise ValueError("FOV specification cannot be empty")
    if ";" in normalized:
        raise ValueError("Use commas to separate FOVs; semicolons are not supported")

    fovs: List[int] = []
    parts = [part for part in normalized.split(",") if part]

    for part in parts:
        if "-" in part:
            start_str, end_str = part.split("-", 1)
            if not start_str or not end_str:
                raise ValueError(f"Invalid range '{part}': missing start or end value")
            try:
                start, end = int(start_str), int(end_str)
            except ValueError as exc:
                raise ValueError(f"Invalid range '{part}': values must be integers") from exc
            if start < 0 or end < 0:
                raise ValueError(f"Invalid range '{part}': negative values not allowed")
            if start > end:
                raise ValueError(f"Invalid range '{part}': start must be <= end")
            fovs.extend(range(start, end + 1))
        else:
            try:
                value = int(part)
            except ValueError as exc:
                raise ValueError(f"Invalid FOV '{part}': must be an integer") from exc
            if value < 0:
                raise ValueError(f"FOV '{part}' must be >= 0")
            fovs.append(value)

    return sorted(set(fovs))


def parse_fovs_field(value: Any) -> List[int]:
    """Normalize a FOV specification originating from YAML."""
    if isinstance(value, list):
        normalized: List[int] = []
        for entry in value:
            try:
                fov = int(entry)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"FOV value '{entry}' is not a valid integer") from exc
            if fov < 0:
                raise ValueError(f"FOV value '{entry}' must be >= 0")
            normalized.append(fov)
        return sorted(set(normalized))
    if isinstance(value, str):
        return parse_fov_range(value)
    raise ValueError("FOV specification must be a list of integers or a comma-separated string")


def read_samples_yaml(path: Path) -> dict[str, Any]:
    """Load a samples YAML specification."""
    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError("Samples YAML must contain a mapping at the top level")
    samples = data.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Samples YAML must include a 'samples' list")
    return data

"""Type definitions for convert wizard."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConvertPageData:
    """Data storage for convert wizard pages."""

    input_path: Path | None = None
    output_dir: Path | None = None
    mode: str = "multi"  # "multi" or "split"
    convert_success: bool = False
    convert_message: str = ""
    output_files: list[Path] = field(default_factory=list)


@dataclass
class ConvertConfig:
    """Configuration for convert operation."""

    input_path: Path
    output_dir: Path
    mode: str  # "multi" or "split"

    @classmethod
    def from_page_data(cls, page_data: ConvertPageData) -> ConvertConfig | None:
        """Create ConvertConfig from page data.

        Args:
            page_data: Page data containing user inputs

        Returns:
            ConvertConfig if valid, None otherwise
        """
        if not page_data.input_path or not page_data.output_dir:
            return None

        return cls(
            input_path=page_data.input_path,
            output_dir=page_data.output_dir,
            mode=page_data.mode,
        )


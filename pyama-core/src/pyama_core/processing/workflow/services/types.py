"""Dataclasses shared across workflow services to avoid circular imports."""

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class Channels:
    pc: int | None = None
    fl: list[int] = field(default_factory=list)


@dataclass(slots=True)
class ResultsPathsPerFOV:
    pc: tuple[int, Path] | None = None
    fl: list[tuple[int, Path]] = field(default_factory=list)
    seg: tuple[int, Path] | None = None
    seg_labeled: tuple[int, Path] | None = None
    fl_corrected: list[tuple[int, Path]] = field(default_factory=list)
    traces_csv: list[tuple[int, Path]] = field(default_factory=list)


@dataclass(slots=True)
class ProcessingContext:
    output_dir: Path | None = None
    channels: Channels | None = None
    results_paths: dict[int, ResultsPathsPerFOV] | None = None
    params: dict | None = None
    time_units: str | None = None


def ensure_results_paths_entry() -> ResultsPathsPerFOV:
    return ResultsPathsPerFOV()


def ensure_context(ctx: ProcessingContext | None) -> ProcessingContext:
    if ctx is None:
        return ProcessingContext(
            channels=Channels(),
            results_paths={},
            params={},
        )

    if ctx.channels is None:
        ctx.channels = Channels()

    if ctx.results_paths is None:
        ctx.results_paths = {}

    if ctx.params is None:
        ctx.params = {}

    return ctx


__all__ = [
    "Channels",
    "ResultsPathsPerFOV",
    "ProcessingContext",
]

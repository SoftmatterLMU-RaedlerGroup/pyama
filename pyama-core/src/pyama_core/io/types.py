"""I/O-related dataclasses to avoid circular imports."""

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ProcessingResults(Mapping[str, Any]):
    project_path: Path
    n_fov: int
    fov_data: dict[int, dict[str, Path]]
    channels: dict[str, Any]
    time_units: str | None
    extra: dict[str, Any] = field(default_factory=dict)

    def __getitem__(self, key: str) -> Any:
        core = self._core_mapping()
        if key in core:
            return core[key]
        if key in self.extra:
            return self.extra[key]
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        yielded = set()
        for key in self._core_mapping():
            yielded.add(key)
            yield key
        for key in self.extra:
            if key not in yielded:
                yield key

    def __len__(self) -> int:
        return len(set(self._core_mapping()) | set(self.extra))

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def to_dict(self) -> dict[str, Any]:
        combined = dict(self._core_mapping())
        combined.update(self.extra)
        return combined

    def _core_mapping(self) -> dict[str, Any]:
        return {
            "project_path": self.project_path,
            "n_fov": self.n_fov,
            "fov_data": self.fov_data,
            "channels": self.channels,
            "time_units": self.time_units,
        }


__all__ = [
    "ProcessingResults",
]

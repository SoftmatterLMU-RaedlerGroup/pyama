"""Job types and models."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class JobStatus(str, Enum):
    """Job status enumeration."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class JobProgress:
    """Job progress information."""

    current: int = 0
    total: int = 0
    percentage: float = 0.0
    message: str = ""


@dataclass
class Job:
    """Job information."""

    job_id: str
    status: JobStatus
    progress: JobProgress = field(default_factory=JobProgress)
    message: str = ""
    result: Optional[dict[str, Any]] = None
    error: Optional[str] = None
    cancelled: bool = False

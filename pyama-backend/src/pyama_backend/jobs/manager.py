"""Job manager for tracking workflow and analysis jobs."""

import logging
import threading
import uuid
from typing import Optional

from pyama_backend.jobs.types import Job, JobProgress, JobStatus

logger = logging.getLogger(__name__)


class JobManager:
    """Manages workflow and analysis jobs."""

    def __init__(self) -> None:
        """Initialize job manager."""
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create_job(self, job_id: Optional[str] = None) -> str:
        """Create a new job and return its ID.

        Args:
            job_id: Optional custom job ID. If not provided, generates a UUID.

        Returns:
            Job ID
        """
        if job_id is None:
            job_id = f"job_{uuid.uuid4().hex[:8]}"

        with self._lock:
            job = Job(
                job_id=job_id,
                status=JobStatus.PENDING,
                message="Job created",
            )
            self._jobs[job_id] = job
            logger.info("Created job: %s", job_id)

        return job_id

    def get_job(self, job_id: str) -> Optional[Job]:
        """Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job if found, None otherwise
        """
        with self._lock:
            return self._jobs.get(job_id)

    def update_status(
        self,
        job_id: str,
        status: JobStatus,
        message: str = "",
        error: Optional[str] = None,
    ) -> None:
        """Update job status.

        Args:
            job_id: Job ID
            status: New status
            message: Status message
            error: Error message if status is FAILED
        """
        with self._lock:
            if job_id not in self._jobs:
                logger.warning("Job not found: %s", job_id)
                return

            job = self._jobs[job_id]
            job.status = status
            job.message = message
            if error:
                job.error = error

            logger.info("Updated job %s status to %s: %s", job_id, status, message)

    def update_progress(
        self,
        job_id: str,
        current: int,
        total: int,
        message: str = "",
    ) -> None:
        """Update job progress.

        Args:
            job_id: Job ID
            current: Current progress value
            total: Total progress value
            message: Progress message
        """
        with self._lock:
            if job_id not in self._jobs:
                logger.warning("Job not found: %s", job_id)
                return

            job = self._jobs[job_id]
            job.progress = JobProgress(
                current=current,
                total=total,
                percentage=(current / total * 100) if total > 0 else 0.0,
                message=message,
            )
            job.message = message

            logger.debug(
                "Updated job %s progress: %d/%d (%.1f%%)",
                job_id,
                current,
                total,
                job.progress.percentage,
            )

    def set_result(self, job_id: str, result: dict) -> None:
        """Set job result.

        Args:
            job_id: Job ID
            result: Result dictionary
        """
        with self._lock:
            if job_id not in self._jobs:
                logger.warning("Job not found: %s", job_id)
                return

            job = self._jobs[job_id]
            job.result = result
            job.status = JobStatus.COMPLETED
            job.message = "Job completed successfully"

            logger.info("Set result for job: %s", job_id)

    def cancel_job(self, job_id: str) -> bool:
        """Cancel a job.

        Args:
            job_id: Job ID

        Returns:
            True if job was cancelled, False if not found
        """
        with self._lock:
            if job_id not in self._jobs:
                logger.warning("Job not found: %s", job_id)
                return False

            job = self._jobs[job_id]
            if job.status in (
                JobStatus.COMPLETED,
                JobStatus.FAILED,
                JobStatus.CANCELLED,
            ):
                logger.warning(
                    "Cannot cancel job %s with status %s", job_id, job.status
                )
                return False

            job.cancelled = True
            job.cancel_event.set()
            job.status = JobStatus.CANCELLED
            job.message = "Job cancelled by user"

            logger.info("Cancelled job: %s", job_id)
            return True

    def list_jobs(self) -> list[Job]:
        """List all jobs.

        Returns:
            List of all jobs
        """
        with self._lock:
            return list(self._jobs.values())

    def delete_job(self, job_id: str) -> bool:
        """Delete a job.

        Args:
            job_id: Job ID

        Returns:
            True if job was deleted, False if not found
        """
        with self._lock:
            if job_id not in self._jobs:
                return False

            del self._jobs[job_id]
            logger.info("Deleted job: %s", job_id)
            return True

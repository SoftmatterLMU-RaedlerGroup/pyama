"""Global application state for PyAMA backend."""

from pyama_backend.jobs.manager import JobManager

# Shared job manager instance used by all routers
job_manager = JobManager()

__all__ = ["job_manager"]

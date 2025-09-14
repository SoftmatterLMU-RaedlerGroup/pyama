"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

import logging

from .pipeline import run_complete_workflow
from .services.types import ProcessingContext

# Configure a simple logger for the workflow package to hide module names
_workflow_logger = logging.getLogger("pyama_core.workflow")
if not _workflow_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    _workflow_logger.addHandler(_handler)
    _workflow_logger.setLevel(logging.INFO)
    _workflow_logger.propagate = False

__all__ = ["ProcessingContext", "run_complete_workflow"]

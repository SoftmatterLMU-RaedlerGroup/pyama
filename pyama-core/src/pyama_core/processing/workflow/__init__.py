"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from pyama_core.processing.workflow.run import run_complete_workflow
from pyama_core.types.processing import (
    ProcessingContext,
    ensure_context,
)

__all__ = ["run_complete_workflow", "ProcessingContext", "ensure_context"]

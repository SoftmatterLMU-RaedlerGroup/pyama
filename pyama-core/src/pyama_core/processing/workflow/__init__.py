"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from .pipeline import run_complete_workflow
from .services.types import ProcessingContext, ensure_context

__all__ = ["run_complete_workflow", "ProcessingContext", "ensure_context"]

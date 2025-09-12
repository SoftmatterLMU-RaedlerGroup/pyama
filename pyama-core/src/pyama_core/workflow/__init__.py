"""
Workflow pipeline for microscopy image analysis.
Consolidates types, helpers, and the orchestration function.
"""

from .pipeline import ProcessingContext, run_complete_workflow

__all__ = ["ProcessingContext", "run_complete_workflow"]

from pyama_core.processing.tracking.iou import track_cell as track_cell_iou
from pyama_core.processing.tracking.btrack import track_cell as track_cell_btrack

# Default export for backward compatibility
track_cell = track_cell_iou

__all__ = ["track_cell", "track_cell_iou", "track_cell_btrack"]

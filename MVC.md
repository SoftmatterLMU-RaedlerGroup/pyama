# PyAMA-Qt Controller Architecture

This document summarizes the strict PySide6 MVC pattern followed by the PyAMA-Qt
application after the recent refactor.

## Guiding Rules

1. **Signal Direction**
   - **View → Controller:** Qt signals only (e.g., button clicks, selections).
   - **Controller → Model:** Direct method/property calls on models.
   - **Model → Controller:** Qt signals emitted by models.
   - **Controller → View:** Direct method calls on widgets or view helpers.

2. **Component Responsibilities**
   - **Models**
     - Expose imperative setters/getters.
     - Emit signals when state changes.
     - Never reference controllers or views.
     - Never receive Qt signals.
   - **Views**
     - Contain UI widgets and layout code.
     - Emit signals describing user intent.
     - Offer idempotent setters for controllers to bind data.
     - Never call models or controllers directly.
   - **Controllers**
     - Own references to the view and relevant models.
     - Connect all signals in `__init__`.
     - Translate view events into model updates and vice versa.
     - Handle long-running work via background workers; capture worker signals,
       update models, and relay status back to the view.
     - Do **not** define/emit custom signals; state is expressed via model/view APIs.

## Controller Overview

Each controller lives under `pyama_qt/controllers/` and follows the same template:

```python
class SomeController(QObject):
    def __init__(self, view: SomePage) -> None:
        super().__init__()
        self._view = view
        self._model = SomeModel()

        self._connect_view_signals()
        self._connect_model_signals()
        self._initialise_view_state()
```

Key points:

- `_connect_view_signals()` hooks widget signals to controller handlers.
- `_connect_model_signals()` relays model changes back to view methods.
- View setters expose only the data needed for rendering; they remain unaware of model classes.
- Controllers store no transient Qt state on views; everything is persisted via models or simple
  controller attributes.

### Analysis Controller (`controllers/analysis.py`)

- Owns `AnalysisDataModel`, `FittingModel`, `FittedResultsModel`.
- Handles CSV loading, fitting requests, worker progress, and plot rendering.
- Calls out to the view panels (`AnalysisDataPanel`, `AnalysisFittingPanel`, `AnalysisResultsPanel`)
  via dedicated setter methods.

### Processing Controller (`controllers/processing.py`)

- Coordinates the workflow configuration, launch, and merge operations.
- Drives `ProcessingConfigPanel` and `ProcessingMergePanel` using plain data payloads.
- Maintains `ProcessingConfigModel` and `WorkflowStatusModel`; background workers update models
  and cascaded view state.

### Visualization Controller (`controllers/visualization.py`)

- Manages project discovery, FOV loading, image display, and trace inspection.
- Keeps `ProjectModel`, `ImageCacheModel`, `TraceTableModel`, `TraceFeatureModel`, and
  `TraceSelectionModel` in sync with the page widgets.
- Responds to view events (`project_load_requested`, data type selection, trace toggles) and
  updates the corresponding models/views directly.

## View Expectations

Every view/panel class exports the minimum surface for controllers:

- Signals describing user actions (`csv_selected`, `fit_requested`, `merge_requested`, etc.).
- Methods to receive controller updates (`render_plot`, `set_parameter_defaults`,
  `set_available_data_types`, `set_trace_dataset`, etc.).

Views never:
- Instantiate or mutate models.
- Emit signals in response to model changes.
- Store references to controllers.

## Background Workers

Long-running tasks (e.g., CSV fitting, ND2 loading, visualization preprocessing) are implemented as
QObject workers:

- Emit status/error/finished signals.
- Controllers connect worker signals to private handlers.
- Controllers manage worker lifecycle (`start_worker`, stop/cancel logic).

Workers **are** allowed to emit signals because they operate in isolation threads/processes,
but controllers are the only consumers of those signals.

## Summary

The architecture enforces a single direction of dependency:

```
View --signals--> Controller --methods--> Model
Model --signals--> Controller --methods--> View
```

This guarantees predictable data flow, simplifies testing, and keeps the Qt widgets free from
business logic.

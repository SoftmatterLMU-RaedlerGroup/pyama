# Qt MVC Migration Plan for PyAMA Qt

## Decision

- Adopt Qt’s native Model/View programming patterns (QAbstractItemModel, QItemSelectionModel, data-aware delegates) across `analysis`, `processing`, and `visualization` pages.
- Remove the bespoke `state.py` dataclasses and `_update_state` mutation helpers that currently mirror NamedTuple semantics but lack compile-time and runtime guarantees.
- Treat controllers as orchestration layers that coordinate domain services and long-running workers while exposing models to the UI.

## Why Move Away from `state.py`

- **Mismatch with dataclasses**: Controllers still call `state._replace`, a leftover from NamedTuple usage, which silently fails and risks stale UI because dataclasses do not implement `_replace`.
- **Hidden coupling**: Pages depend on `BasePage.diff_states` + dataclass snapshots, requiring manual diffs to trigger UI refreshes.
- **Signal fan-out**: Controllers emit entire state instances via `state_changed` on every mutation, creating unnecessary object churn and awkward partial updates.
- **Qt duplication**: Qt already offers granular change notification via `dataChanged` / `modelReset` so we can rely on framework semantics instead of reimplementing observers.

## Target Architecture Overview

- **Models**: Introduce Qt model classes that own domain data and emit standard Qt signals.
  - `analysis`: `TraceTableModel`, `FittingResultsModel`, `PlotSeriesModel` (custom QObject + signals for Matplotlib canvas).
  - `processing`: `ProcessingConfigModel` (parameters + channels using `QStandardItemModel` or property-based QObject), `MicroscopyMetadataModel`, `WorkflowStatusModel` (for long-running jobs).
  - `visualization`: `ProjectModel`, `ImageCacheModel`, `TraceTableModel`, `TraceFeatureModel`, `TraceSelectionModel`.
- **Controllers**: Remain `QObject` subclasses but switch to mutating models instead of dataclass instances. They mediate background workers and update models through Qt APIs.
- **Views/Pages**: Bind widgets to models using `setModel`, `QItemSelectionModel`, `QDataWidgetMapper`, and specialized delegates. Remove `set_state`/`diff_states` flows. Introduce light-weight mixins (`ModelBoundPage`, `ModelBoundPanel`) for pages/panels that only consume Qt models.
- **Workers**: Continue to use `start_worker`, but results are injected into models (e.g., `TraceTableModel.load_dataframe`). Models emit `modelReset` / `dataChanged` to refresh views.

## Migration Plan

1. **Preparation & Scaffolding**

   - Audit where each `state` dataclass is read/written; document field ownership and consumers.
   - Introduce a `models/` package under each domain to host new Qt model classes.
   - Provide a thin compatibility layer so existing controllers can expose both legacy state and new models during transition (e.g., keep `state_changed` but emit models).

2. **Refactor Shared UI Base Classes**

   - Deprecate `BasePage.diff_states` and `BasePanel.set_state` methods.
   - Introduce mixins/helpers for binding Qt models (e.g., `ModelBoundPage`, `ModelBoundPanel`).
   - Update pages to subscribe to model signals (slots) instead of `set_state`.

3. **Analysis Domain Migration (Pilot)**

   - Implement `TraceTableModel` (inherits `QAbstractTableModel`) to expose loaded CSV data.
   - Implement `FittingResultsModel` for fitted data (supports incremental row insertion).
   - Replace `AnalysisState` usage in controller with direct model updates; remove `_update_state` and `_prepare_all_plot` in favor of model methods.
   - Adapt `AnalysisDataPanel`, `AnalysisFittingPanel`, `AnalysisResultsPanel` to consume models (`setModel`, `selectionModel`).
   - Validate UI parity; add regression tests using Qt Test to exercise model/view bindings.

4. **Processing Domain Migration**

   - Create `ProcessingConfigModel` encapsulating parameters + channels, exposing properties/signals for widgets.
   - Introduce `WorkflowStatusModel` to publish status, progress, and error strings (replace `status_message` / `error_message`).
   - Update `ProcessingController` to mutate models and stop emitting `state_changed`.
   - Refactor panels (`workflow_panel`, `merge_panel`) to bind to new models.

5. **Visualization Domain Migration** (✅ implemented 2025‑09‑26)

   - Replace `VisualizationState` dataclass with dedicated Qt models (`ProjectModel`, `ImageCacheModel`, `TraceTableModel`, `TraceFeatureModel`, `TraceSelectionModel`).
   - Expose request dataclasses via `visualization/requests.py` for controller APIs (`ProjectLoadRequest`, `VisualizationRequest`, `TraceSelectionRequest`, `FrameNavigationRequest`, `DataTypeChangeRequest`).
   - Update `VisualizationController` to mutate models, eliminate `_update_state`, and emit granular status/error signals only.
   - Convert `VisualizationPage` to `ModelBoundPage` and wire models in `bind()`; remove `set_state` usage.
   - Refactor panels (`project_panel`, `image_panel`, `trace_panel`) to subclass `ModelBoundPanel`, subscribe to model signals, and expose domain-specific `set_models(...)` entry points.
   - Introduce shared helpers (e.g., `ImageCacheModel.set_images`, `TraceTableModel.reset_traces`) so worker callbacks push data directly into models.
   - Documented request/model surface in code comments to serve as template for analysis/processing refactors.

6. **Cleanup & Removal**

   - ✅ `visualization/state.py` deleted; controllers/panels updated accordingly.
   - Pending: delete `analysis/state.py` and `processing/state.py` after their migrations.
   - Remove `state_changed`/`status_changed` signals that broadcast full state objects; replace with targeted model signals or dedicated status QObjects (in progress—analysis/processing still emit).
   - Simplify services (e.g., `WorkerHandle`) to update models directly and ensure thread-safety (use `Qt.invokeMethod` or queued connections).

7. **Testing & Verification**
   - Extend test suite with model-specific behavior: row counts, data roles, selection propagation, signal emission on updates.
   - Perform manual UI regression for the three domains to confirm parity.
   - Profile UI responsiveness; ensure large CSV loads leverage `beginResetModel`/`endResetModel` for atomic updates.

## Additional Considerations

- **Threading**: Ensure background worker callbacks use `Qt.QueuedConnection` when mutating models to keep updates on the UI thread.
- **Undo/Redo**: Qt models enable easy adoption of `QUndoStack` if needed later; keep APIs amenable to command-based updates.
- **Documentation**: Update developer docs to emphasize Qt MVC patterns and remove references to manual state tracking.
- **Incremental Delivery**: Ship after each domain migration with feature flags or branch gating to avoid destabilizing the entire UI at once.

## Success Criteria

- No `state.py` modules remain; their fields are represented in Qt models or domain services.
- Views no longer call `set_state` or diff dataclasses; they react entirely through Qt’s model/view signals.
- Controllers expose typed models and minimal imperative API surface (start/cancel actions only).
- Existing features (CSV load, fitting, workflow execution, visualization) behave identically or better, with improved maintainability and easier UI updates.

## Visualization Implementation Reference

Use the visualization stack as the blueprint for migrating other domains.

- **Modules & Data Flow**

  - `visualization/requests.py`: request dataclasses replacing ad-hoc dict usage.
  - `visualization/models.py`: Qt models encapsulating project metadata, image cache, trace tables/features, and active selection signaling.
  - `visualization/controller.py`: orchestrates workers, mutates models, exposes granular status/error signals; no state dataclass.
  - `visualization/page.py`: `ModelBoundPage` that wires controller models into panels during `bind()` and listens only for error/status signals.
  - `visualization/panels/*.py`: each is a `ModelBoundPanel` with `set_models(...)`, connects to model signals, and raises domain signals back to controller.

- **Cross-Cutting Utilities**

  - `ui/base.py`: added `ModelBoundPage` / `ModelBoundPanel` mixins for model-driven views.
  - `ui/__init__.py`: re-export new mixins so other modules can adopt them without deep imports.
  - `ParameterPanel.set_parameters` now accepts plain dicts, easing migration for processing forms.

- **Runtime Checks**

  - `uv run pyama-qt` validates that processing, analysis, and visualization tabs load without dataclass state.
  - Ensure new model bindings (e.g., `ImageCacheModel.set_images`, `TraceTableModel.reset_traces`) emit `modelReset`/`dataChanged` to refresh associated widgets.

- **Migration Checklist for Other Domains**
  1. Create request dataclasses for controller entry points (similar to `visualization/requests.py`).
  2. Introduce Qt model classes to hold domain data; emit focused signals instead of broadcasting whole dataclass instances.
  3. Update controller to own models, drop `_update_state`, and expose model properties for the UI to subscribe to.
  4. Convert page to `ModelBoundPage`, bind controller models in `bind()`, and remove `set_state` calls.
  5. Refactor panels to `ModelBoundPanel`, add `set_models(...)`, and move all state handling to model signals.
  6. Remove the old `state.py` module and clean up imports.
  7. Run `uv run pyama-qt` (or domain-specific tests) to catch regressions.

Refer back to the visualization implementation when porting analysis/processing—mirroring the structure will minimize surprises.

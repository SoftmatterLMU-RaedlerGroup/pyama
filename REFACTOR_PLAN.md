# PyAMA Refactor Plan

## Scope
- Keep existing behaviour intact; focus on naming, structure, and clarity.
- Do not modify `pyama_core/analysis`, `pyama_core/workflow`, or `pyama_core/io/nikon` beyond import path updates that become strictly necessary.
- Primary targets are the Qt UI modules and shared IO helpers that feed them.

## Guiding Principles
- Prefer small, explicit components with single responsibilities.
- Adopt consistent vocabulary: `Page` for top-level tabs, `Panel` for primary columns, `Section` for grouped controls, and `Component` for reusable widgets.
- Favor typed payload objects or dataclasses over loosely-typed dicts for cross-module communication.
- Keep UI logic minimal; move orchestration into lightweight controller or service classes.

## UI Restructure Overview
1. **Introduce shared scaffolding**
   - Create `pyama_qt/ui/base.py` with `BasePage` and `BasePanel` that provide `build()`, `bind()`, and `set_state()` hooks plus shared dialog helpers.
   - Add `pyama_qt/services/threading.py` to encapsulate the current `QThread` setup code used by analysis and processing.
   - Move reusable widgets (e.g., `SampleTable`, `ParameterPanel`, `MplCanvas`) into `pyama_qt/components/` while keeping public APIs compatible.
2. **Extract controllers**
   - For each tab, introduce a controller module (`analysis/controller.py`, `processing/controller.py`, `visualization/controller.py`) that owns state, background work, and signals.
   - Pages become thin view classes that delegate to their controller and consume typed state objects (`AnalysisState`, `ProcessingState`, etc.).
3. **Normalize naming & layout**
   - Rename modules and classes to follow the shared vocabulary (e.g., `workflow.py` → `processing_panel.py`, `MergePanel` → `ProcessingMergePanel`).
   - Replace ad-hoc signal names with past-tense events like `sampleLoaded`, `processingRequested`, and ensure payloads are typed via dataclasses.
4. **Clean separation of concerns**
   - Remove parent back-references inside widgets by passing explicit `Props` objects and emitting signals upward.
   - Consolidate dialog and file chooser helpers to avoid duplicated logic across panels.

## IO Helper Refactor
- Split `pyama_core/io/processing_csv.py` into a package:
  - `loader.py` handles file reading and default column normalization.
  - `validators.py` stores schema checks, leaving UI code to call a single `validate()`.
  - `mappers.py` converts DataFrames into domain dictionaries (feature maps, metadata).
  - Re-export legacy symbols from `pyama_core/io/processing_csv/__init__.py` to keep the public API stable.
- Mirror the pattern for analysis CSV helpers by introducing a thin facade (e.g., `pyama_core/io/analysis_api.py`) used by UI controllers.

## Phased Execution
1. **Scaffolding**: Introduce base classes, services, and components directory; adjust imports only.
2. **Controller Extraction**: Migrate processing logic first, followed by analysis and visualization.
3. **Naming Pass**: Apply consistent module/class names and update exports.
4. **IO Helper Split**: Restructure `processing_csv` and update consumers.
5. **State & Signals**: Introduce shared state dataclasses and harmonize signal names/types.
6. **Verification**: Run existing tests, add controller-focused unit tests, and document changes in `pyama-qt/README.md`.

## Testing & Verification
- Run the full test suite after each major phase.
- Add smoke tests for controller-service boundaries where practical.
- Document any temporary gaps or follow-up tasks in this file as the refactor progresses.

## Open Decisions
- Final directory placement for controllers (alongside pages vs. under `services/`).
- Whether to expose controllers publicly or keep them internal to `pyama_qt`.
- Additional helper abstractions for file dialogs if further duplication is discovered.

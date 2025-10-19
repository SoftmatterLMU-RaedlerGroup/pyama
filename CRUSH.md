# PyAMA Development Commands

## Documentation Synchronization
**IMPORTANT**: When updating this file (CRUSH.md), AGENTS.md, or CLAUDE.md, sync the changes to all three files to maintain consistency across the repository documentation.

## Environment Setup
```bash
uv sync --all-extras
uv pip install -e pyama-core/ -e pyama-qt/
```

## Core Commands
- Run GUI: `uv run pyama-qt`
- Test all: `uv run pytest`
- Test single file: `uv run pytest tests/test_workflow.py`
- Lint: `uv run ruff check`
- Format: `uv run ruff format`
- Type check: `uv run ty check`

## Processing Outputs
- Workflow results are stored in `processing_results.yaml`, where `channels.pc` is `[phase_channel, [feature1, ...]]`, `channels.fl` is `[[channel, [feature1, ...]], ...]`, and a `results` map is keyed by FOV.
- Each FOV now produces a single merged traces CSV (`*_traces.csv`) whose feature columns are suffixed with `_ch_{channel}` (e.g., `intensity_total_ch_1`, `area_ch_0`). Legacy per-channel CSVs are still read but no longer written.

## Code Style Guidelines
- Python 3.11+ with 4-space indentation
- Type hints required: use built-in generics (dict, list) over typing.Dict
- snake_case for modules/functions, PascalCase for classes
- **Private variables/methods: prefix with `_` (e.g., `_private_var`, `_private_method()`)**
- **Public variables/methods: no leading underscore (e.g., `public_var`, `public_method()`)**
- **All classes are public (no leading underscore for class names)**
- Use pathlib.Path for filesystem operations
- Logging via module-level loggers
- Qt uses simplified tab-based structure (not strict MVC)
- **All Qt widget classes must use `_build_ui()` and `_connect_signals()` methods for initialization**
- **Signal naming: use snake_case (e.g., `status_message.emit()`, not `statusMessage.emit()`)**
- **All signal receiver methods (methods connected to signals) must use `@Slot()` decorator for performance and type safety**
  - Public slots: `@Slot()` or `@Slot(type)` for methods like `on_fitting_completed(self, data: pd.DataFrame)`
  - Private slots: `@Slot()` for methods like `_on_button_clicked(self)`
- **Import style: Use absolute imports only - no relative imports (`.module` or `..parent.module`**)
- **All import statements must be at the top of the file** - no scattered imports within functions
- Group code with structured comment separators:
  - Major sections: `# ============================================================================= # SECTION NAME # =============================================================================`
  - Subsections: `# ------------------------------------------------------------------------ # SUBSECTION # ------------------------------------------------------------------------`
- **Method organization guidelines:**
  - Group related functionality together (e.g., worker callbacks with their requester)
  - Avoid redundant section headers like "WORKER CALLBACKS" when methods flow logically together
  - Use descriptive, functional section names (e.g., "VISUALIZATION REQUEST" instead of "PUBLIC API - SLOTS FOR EXTERNAL CONNECTIONS")
  - Keep rendering methods within their logical groups (e.g., frame rendering in FRAME MANAGEMENT)
- Never commit secrets; follow ruff warnings resolution
- **Centralize dataclass definitions in `src/pyama_qt/types/` organized by functional area**
  - `types/analysis.py` for analysis-related data structures
  - `types/visualization.py` for visualization-related data structures  
  - `types/processing.py` for processing-related data structures

## One-Way UI→Model Binding Architecture
**IMPORTANT**: PyAMA-QT uses strict one-way binding from UI to model only. This prevents circular dependencies and makes data flow predictable.

### Requirements:
- **UI→Model only**: User input updates model state, but models don't automatically update UI
- **No model→UI synchronization**: UI refreshes must be explicit, not automatic
- **Signal-based communication**: Cross-panel updates via explicit Qt signals
- **Manual mode pattern**: Parameter panels only update model when user enables manual editing
- **Direct assignment**: UI event handlers directly update model attributes

### Implementation Pattern:
```python
@Slot()
def _on_ui_widget_changed(self) -> None:
    """Handle UI widget change (UI→Model only)."""
    # Get value from UI widget
    ui_value = self._ui_widget.current_value()
    
    # Update model directly (one-way binding)
    self._model_attribute = ui_value
    
    # Optionally emit signal for other panels
    self.model_changed.emit()
```

### Forbidden Patterns:
- Automatic UI updates when model changes
- Bidirectional data binding
- Signal loops where UI changes trigger model changes which trigger UI changes
- Model→UI automatic synchronization

### Allowed Patterns:
- Initial UI population from model defaults
- Manual UI refresh methods called explicitly
- Cross-panel communication via signals
- Background workers loading data into model

### Reference Documentation:
See `pyama-qt/UI_MODEL_BINDINGS.md` for detailed panel-by-panel analysis and examples.

## Signal Architecture Guidelines
**IMPORTANT**: Child panels should only emit semantic signals, not generic status messages. Use meaningful signals that describe the actual events and their outcomes.

### Requirements:
- **Semantic signals only**: Use signals like `workflow_finished(success, message)` instead of generic `status_message(text)`
- **Event-specific signals**: Each major operation should have its own started/finished signal pair
- **Rich data payload**: Signals should include relevant data (success status, results, error details)
- **No redundant status messages**: Don't emit generic status messages when semantic signals already convey the same information

### Examples:
```python
# GOOD: Semantic signals
workflow_started = Signal()
workflow_finished = Signal(bool, str)  # success, message
microscopy_loading_started = Signal()
microscopy_loading_finished = Signal(bool, str)

# BAD: Generic status message
status_message = Signal(str)  # Should be removed
```

### Implementation Pattern:
- Child panels emit semantic signals for major events
- Main tab connects to semantic signals and updates status bar accordingly
- All status text is generated centrally in main tab handlers, not scattered across child panels
- Error conditions are propagated through semantic signal parameters

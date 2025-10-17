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
- Type check: `uv run ty`

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
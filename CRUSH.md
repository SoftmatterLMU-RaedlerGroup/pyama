# PyAMA Development Commands

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
- Use pathlib.Path for filesystem operations
- Logging via module-level loggers
- Qt uses simplified tab-based structure (not strict MVC)
- **All Qt widget classes must use `_build_ui()` and `_connect_signals()` methods for initialization**
- Group code with structured comment separators:
  - Major sections: `# ============================================================================= # SECTION NAME # =============================================================================`
  - Subsections: `# ------------------------------------------------------------------------ # SUBSECTION # ------------------------------------------------------------------------`
- Never commit secrets; follow ruff warnings resolution
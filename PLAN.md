# Upcoming Workflow Data Restructuring Plan

1. **Rename Workflow Context Outputs**
   - Replace `results_paths` with `results` across `ProcessingContext`, serialization helpers, YAML schema, and UI consumers.
   - Update any persistence and deserialization code to accept both the new and legacy names for backward compatibility.

2. **Consolidate Trace CSV Outputs**
   - Modify `ExtractionService` to merge per-channel trace data into a single CSV per FOV using feature suffixes like `intensity_total_ch_1` and `area_ch_0`.
   - Adjust `Results` tracking to reference the unified CSV and update downstream readers/tests accordingly.

3. **Revise UI and Tests**
   - Ensure the Qt configuration panel reflects the new single-CSV workflow (e.g., status messaging, expectations).
  - Extend `tests/test_workflow.py` to validate the merged CSV schema and updated context serialization.

4. **Documentation and Migration Notes**
   - Document the schema changes in project docs, highlighting YAML layout updates and CSV format adjustments.
   - Provide guidance for users migrating from existing `processing_results.yaml` files and multiple per-channel CSV outputs.

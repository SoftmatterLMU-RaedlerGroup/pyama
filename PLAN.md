# Upcoming Workflow Data Restructuring Plan

- [x] **Rename Workflow Context Outputs**
  - Replace `results_paths` with `results` across the context dataclasses, pipeline serialization, and YAML helpers (retain backward compatibility when loading legacy files).

- [x] **Consolidate Trace CSV Outputs**
  - Merge per-channel trace data into a single FOV CSV (feature columns suffixed with `_ch_{id}`) and record the unified path in workflow results.

- [x] **Revise UI and Merge Tooling**
  - Update Qt viewers/mergers to consume the unified CSV format by filtering features per channel when needed.

- [ ] **Documentation & Follow-up**
  - Publish migration notes and validate downstream analytics (visualization save/load, sample merge outputs) against representative datasets.

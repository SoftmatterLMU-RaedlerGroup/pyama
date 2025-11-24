# PyAMA Live Single-Cell Array Imaging Refresh (DPG 2026 Poster)

This poster targets the DPG 2026 microscopy audience with an update on PyAMA, a five-year-old workflow that converts ND2 live-cell acquisitions into curated single-cell traces. No new biology is introduced; instead, we document how refurbishing the analysis stack safeguards existing single-cell array assays. The revamped pipeline (copy → LOG-STD segmentation → background correction → IoU tracking → CSV extraction) now runs inside reproducible UV environments with synchronized Qt/CLI front ends so experimenters can monitor every stage from acquisition to fitted traces.

The narrative centers on a practical comparison against standard cultures seeded on flat substrates. Without patterned single-cell arrays, cells meander out of the field of view, drift toward edges, and inflate segmentation errors that must be corrected by hand. PyAMA’s refresh tackles these points directly: (i) border-aware QC flags trajectories whose centroids touch the frame, (ii) ≥30-frame persistence gates remove fleeting cells, and (iii) tunable fluorescence background weighting preserves dynamic range. Reprocessing legacy data shows a twofold rise in usable traces and a threefold drop in field-of-view loss relative to the flat-substrate control, quantifying the value of keeping cells confined.

For the poster, we will focus on three aspects: reliability metrics for longitudinal platforms (uptime, batch reproducibility, QC flags), accuracy gains linked to reduced cell escape (heat maps of FOV retention, trace survival curves), and operator-facing tooling (side-by-side GUI snapshots, automated inspection dashboards). This framing keeps the story technical yet grounded in daily lab pain points, highlighting how infrastructure upkeep maintains scientific accuracy even when the experimental biology remains constant.

## Final Figure Plan

1. **Phase-Contrast Panel (side-by-side)**
   - Representative FOV images for LiSCA vs. flat substrate, same scale/time point, annotated to highlight confinement vs. drift.

2. **Box-Plot Subplots**
   - Left subplot: per-cell time in field of view (hours). Right subplot: mean cell speed (µm/min). Each subplot contains two boxes (LiSCA vs. flat) with whiskers and sample counts, presented on a shared row for visual symmetry.

3. **Dynamic Trace Panel**
   - Two line charts stacked vertically: fluorescence intensity vs. time and cell area vs. time, each showing LiSCA (representative trace + fit) versus flat substrate. Residual std and area CV values called out beside the respective plots.

4. **Optional Supporting Panel**
   - Small QC histogram or GUI snapshot only if white space remains; otherwise, rely on captions/callouts to mention automated QC metrics.

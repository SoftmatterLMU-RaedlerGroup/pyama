# Execution Plan

1) Finish frontend test pages  
   - Build `/test/workflow`, `/test/merge`, `/test/analysis`, `/test/visualization` with the required “Testing Endpoints” bullet list.  
   - Wire forms/polling to processing/analysis/visualization APIs (start job, status, cancel, results, frame preview).  
   - Add loading/error/success states consistent with existing components.

2) Align API client and types  
   - Add any fields needed for new job states or visualization payloads.  
   - Keep typings in `src/types` in sync with the backend responses.

3) Backend polish  
   - Ensure job manager usage is consistent across processing/analysis/visualization.  
   - Verify imports and logging for visualization frame/processing endpoints.

4) Sanity checks  
   - Run `npm run lint` and `npm run type-check`.  
   - Smoke-check backend startup (`uv run python -m pyama_backend`) or import checks.

5) Finalize  
   - Stage changes and commit (e.g., `feat: extend backend job handling and add web test pages`).  
   - Push to the repository.

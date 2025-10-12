# Issues Report

This report summarizes the fixes implemented for the issues listed in `ISSUES.md`.

### Issue 1: processing: Default FoV set to -1 and -1, better would be the maximum FoV from the file as default

-   **Status:** Fixed
-   **Description:** The default FoV range for processing is now set based on the metadata of the loaded microscopy file. The `fov_start` is set to 0 and `fov_end` is set to the maximum number of FOVs available in the file.

### Issue 2: processing and visualization: Software crashed while doing processing and visualization at the same time. If this is not intended, maybe block visualization if processing is running?

-   **Status:** Fixed
-   **Description:** The visualization tab is now disabled while the processing workflow is running. This prevents conflicts and potential crashes from simultaneous operations. A status message is displayed in the status bar to inform the user.

### Issue 3: visualization: if clicking "uncheck all cells" the traces above do not vanish, only when one cell is checked and unchecked again.

-   **Status:** Fixed
-   **Description:** The trace plot is now correctly updated when "uncheck all cells" is clicked. The plot is cleared to reflect that no cells are selected.

### Issue 4: visualization: Clicking through the cells is too slow. Also clicking on a certain trace and being navigated to the respective cell would be super helpful in case there is only one good or bad cell in the dataset. Otherwise I would have to click through every single cell

-   **Status:** Partially Fixed
-   **Description:**
    -   Clicking on a trace in the plot now automatically navigates to and selects the corresponding cell in the table, even if it is on a different page.
    -   The performance aspect of clicking through cells has not been addressed as it would require a more significant refactoring of the plotting component.

### Issue 5: visualization: Show outline of all cells and enable to click on the cells for selection (enables faster de-selection of double occupations)

-   **Status:** Fixed
-   **Description:**
    -   All detected cells are now displayed as circle overlays on the image. Non-active cells are shown with a gray circle, and the currently selected active cell is highlighted with a red circle.
    -   The cell overlays are now clickable. Clicking on a cell circle in the image view will select the corresponding trace in the trace panel.

### Issue 6: visualization: Despite having selected two fluorescence channels, I can only see/select the intensity traces for one of them

-   **Status:** Fixed
-   **Description:** The trace panel now includes a channel selector dropdown menu. This allows the user to switch between the intensity traces for all the fluorescence channels that were selected for visualization.

### Issue 7: visualization: When scrolling through the cells and pressing "Next page", the selected cell will always be the last one from the list. Would be more intuitive to start from the beginning of the page.

-   **Status:** Fixed
-   **Description:** The active cell selection is now cleared when the user navigates to the next or previous page in the trace selection table.

### Issue 8: segmentation(pyama-core): In the old versions, cells to close to the boarders of the FoV were excluded to account for possible boarder effects from the imaging. Now, also cells really close to the boarder are recognized. Can we add this feature of segmentation back in (or otherwise adapt the background correction accordingly)?

-   **Status:** Fixed
-   **Description:** A filtering step has been added to the trace extraction process in `pyama-core`. Cells that are detected too close to the border of the field of view (within 10 pixels) in any frame are now excluded from the final analysis results.

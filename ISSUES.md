- processing: Default FoV set to -1 and -1, better would be the maximum FoV from the file as default
- processing and visualiztion: Software crashed while doing processing and visualization at the same time. If this is not intended, maybe block visualization if processing is running?
- visualization: if clicking "uncheck all cells" the traces above do not vanish, only when one cell is checked and unchecked again.
- visualization: Clicking through the cells is too slow. Also clicking on a certain trace and being navigated to the respective cell would be super helpful in case there is only one good or bad cell in the dataset. Otherwise I would have to click through every single cell
- visualization: Show outline of all cells and enable to click on the cells for selection (enables faster de-selection of double occupations)
- visualization: Depsite having selected two fluorescence channels, I can only see/select the intensity traces for one of them
- visualization: When scrolling through the cells and pressing "Next page", the selected cell will always be the last one from the list. Would be more intuitive to start from the beginning of the page.
- segmentation(pyama-core): In the old versions, cells to close to the boarders of the FoV were excluded to account for possible boarder effects from the imaging. Now, also cells really close to the boarder are recognized. Can we add this feature of segmentation back in (or otherwise adapt the background correction accordingly)?


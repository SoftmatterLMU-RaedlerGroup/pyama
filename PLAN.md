# Parallel Processing Plan: Batch Extraction + Worker Pool

## Overview
Split processing into two stages:
1. **Sequential extraction** of FOV data from ND2 (I/O bound, fast)
2. **Parallel processing** of extracted data (CPU bound, parallelizable)

## Architecture

```
ND2 File → [Batch Extractor] → NPY Files → [Worker Pool] → Results
                                    ↓              ↓
                              fov_0000.npy    Worker 0
                              fov_0001.npy    Worker 1  
                              fov_0002.npy    Worker 2
                              fov_0003.npy    Worker 3
```

## Stage 1: Batch Extraction

**Purpose**: Eliminate ND2 file access contention
- Extract 4 FOVs at once (configurable batch size)
- Save as NPY files (faster than NPZ, no compression overhead)
- Store both phase contrast and fluorescence channels

**Data Structure**:
```
output_dir/
├── fov_0000/
│   ├── 250129_HuH7_fov0000_phase_contrast_raw.npy
│   └── 250129_HuH7_fov0000_fluorescence_raw.npy
├── fov_0001/
│   ├── 250129_HuH7_fov0001_phase_contrast_raw.npy
│   └── 250129_HuH7_fov0001_fluorescence_raw.npy
```

## Stage 2: Parallel Processing

**Worker Design**:
- Each worker is a separate process (true parallelism)
- Workers load NPY files directly (no ND2 access)
- Complete all three steps (binarization → background → traces)
- No inter-worker communication needed

**Process Flow**:
```python
# Main process
for batch in batches:
    extracted_data = extract_batch(batch_fovs)
    with ProcessPool(workers=4) as pool:
        results = pool.map(process_fov, extracted_data)
```

## Updated FOV Folder Contents

Each FOV folder will contain:

### 1. **Raw Extracted Data** (Stage 1 - Batch Extraction)
```
fov_0000/
├── 250129_HuH7_fov0000_phase_contrast_raw.npy      # (n_frames, height, width) uint16
└── 250129_HuH7_fov0000_fluorescence_raw.npy        # (n_frames, height, width) uint16
```

### 2. **Binarization Output** (Modified - no normalized PC)
```
└── 250129_HuH7_fov0000_binarized.npz               # (n_frames, height, width) bool
```

### 3. **Background Correction Output** 
```
└── 250129_HuH7_fov0000_fluorescence_corrected.npz  # (n_frames, height, width) float32
```

### 4. **Trace Extraction Output**
```
└── 250129_HuH7_fov0000_traces.csv                  # Columns: frame, unique_cell_id, x, y, area, mean_intensity, etc.
```

### 5. **Project File** (If using project management)
```
└── pyama_project.toml                               # FOV-specific metadata and processing status
```

## Key Design Decisions

1. **Batch Size = Worker Count**: Process 4 FOVs with 4 workers for optimal resource usage

2. **Memory Management**: 
   - Extract only what's needed for current batch
   - Option to delete raw NPY files after processing
   - Memory-mapped arrays for large datasets

3. **Error Handling**:
   - If extraction fails, skip entire batch
   - If one worker fails, retry that FOV
   - Maintain processing state for resume capability

4. **Progress Tracking**:
   - Stage 1: Track extraction progress
   - Stage 2: Track worker completion
   - Overall: FOVs completed / total FOVs

## Benefits

1. **No ND2 Contention**: Each worker uses independent NPY files
2. **True Parallelism**: Process-based workers bypass GIL
3. **Scalable**: Easy to adjust batch size and worker count
4. **Fault Tolerant**: Can resume from last completed batch
5. **Memory Efficient**: Process only active batch in memory

## Implementation Steps

1. Create `extract_fov_batch()` function to extract NPY files
2. Modify services to accept NPY file paths instead of ND2 reader
3. Create worker function that processes single FOV from NPY files
4. Add batch coordinator to manage extraction → processing pipeline
5. Update test_modules.py with new parallel mode

## Performance Estimate

Current (sequential): ~X seconds per FOV
Proposed (4 workers): ~X/4 seconds per FOV + extraction overhead

Extraction is fast (~2-5 seconds per batch), so overhead is minimal compared to processing gains.

## Storage Optimization

**Option 1 - Keep raw files**:
- Pros: Can reprocess with different parameters
- Cons: ~16 GB per FOV
- Total: ~20 GB per FOV (raw + processed)

**Option 2 - Delete raw after processing**:
- Pros: Only ~4-5 GB per FOV final size
- Cons: Need to re-extract from ND2 for reprocessing
- Total: ~5 GB per FOV (processed only)

## Implementation Changes Needed

1. **Binarization service**: Accept NPY file path instead of ND2 reader
2. **Remove phase contrast normalization step**: Simplify binarization service
3. **Background correction**: Load segmentation from NPZ, fluorescence from NPY
4. **Add cleanup option**: Delete raw NPY files after successful processing

## Processing Flow

```python
# Stage 1: Extract
phase_contrast_raw.npy (uint16) → 
fluorescence_raw.npy (uint16)   →

# Stage 2: Process (in parallel)
Worker 0: phase_contrast_raw.npy → binarized.npz
          fluorescence_raw.npy + binarized.npz → fluorescence_corrected.npz
          binarized.npz + fluorescence_corrected.npz → traces.csv
```
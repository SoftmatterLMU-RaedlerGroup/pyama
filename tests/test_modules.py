#!/usr/bin/env python
"""
Test script for individual PyAMA-Qt processing modules.

This script allows testing each processing step independently:
1. Binarization
2. Background correction
3. Trace extraction

For development use only - all test parameters are configured as constants.
"""

import logging
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pyama_qt.processing.services.binarization import BinarizationService
from pyama_qt.processing.services.background_correction import BackgroundCorrectionService
from pyama_qt.processing.services.trace_extraction import TraceExtractionService
from pyama_qt.processing.services.workflow import WorkflowCoordinator
from pyama_qt.processing.services.copy import CopyService
from pyama_qt.core.data_loading import load_nd2_metadata


# ========== TEST CONFIGURATION - MODIFY THESE FOR YOUR TESTS ==========

# File paths
ND2_FILE = Path("/project/ag-moonraedler/projects/Testdaten/PyAMA/250129_HuH7.nd2")  # UPDATE THIS
OUTPUT_DIR = Path("/project/ag-moonraedler/projects/Testdaten/PyAMA")  # UPDATE THIS

# FOV range
FOV_START = 12  # Starting FOV index (inclusive)
FOV_END = 12    # Ending FOV index (inclusive)

# Channel indices (set to None for auto-detection)
PC_CHANNEL = 0  # Phase contrast channel (None = auto-detect)
FL_CHANNEL = 1  # Fluorescence channel (None = auto-detect)

# Processing parameters
MASK_SIZE = 3           # Mask size for binarization
DIV_HORIZ = 7          # Horizontal divisions for background correction
DIV_VERT = 5           # Vertical divisions for background correction
MIN_TRACE_LENGTH = 10   # Minimum trace length threshold (increased to filter out transient detections)

# Parallel processing parameters (only used in workflow test)
BATCH_SIZE = 4          # Number of FOVs to extract at once in workflow
N_WORKERS = 4           # Number of parallel workers in workflow
DELETE_RAW = False      # Delete raw NPY files after processing

# Logging
VERBOSE = True  # Set to False for less detailed output


# =====================================================================


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%H:%M:%S"
    )


def test_binarization(
    nd2_file: Path,
    output_dir: Path,
    fov_start: int,
    fov_end: int,
    mask_size: int = 3,
    pc_channel: int | None = None
) -> bool:
    """
    Test binarization on specified FOVs.
    
    Args:
        nd2_file: Path to ND2 file
        output_dir: Output directory
        fov_start: Starting FOV index (inclusive)
        fov_end: Ending FOV index (inclusive)
        mask_size: Mask size for binarization
        pc_channel: Phase contrast channel index (auto-detect if None)
    
    Returns:
        bool: True if successful
    """
    logger = logging.getLogger("test_binarization")
    logger.info(f"Testing binarization on FOVs {fov_start}-{fov_end}")
    
    # First check if NPY files exist
    missing_npy = []
    for fov_idx in range(fov_start, fov_end + 1):
        fov_dir = output_dir / f"fov_{fov_idx:04d}"
        npy_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_phase_contrast_raw.npy"
        if not npy_file.exists():
            missing_npy.append(fov_idx)
    
    if missing_npy:
        logger.error(f"Missing NPY files for FOVs: {missing_npy}")
        logger.error("Please run 'python test_modules.py copy' first to extract NPY files")
        return False
    
    # Load metadata
    try:
        metadata = load_nd2_metadata(str(nd2_file))
        logger.info(f"Loaded ND2 file: {metadata['filename']}")
        logger.info(f"Channels: {metadata['channels']}")
        logger.info(f"FOVs: {metadata['n_fov']}")
        
        # Auto-detect phase contrast channel if not provided
        if pc_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'phase' in channel.lower() or 'pc' in channel.lower():
                    pc_channel = i
                    logger.info(f"Auto-detected phase contrast channel: {i} ({channel})")
                    break
            
            if pc_channel is None:
                logger.warning("Could not auto-detect phase contrast channel, using channel 0")
                pc_channel = 0
                
    except Exception as e:
        logger.error(f"Failed to load ND2 metadata: {e}")
        return False
    
    # Create binarization service
    service = BinarizationService()
    
    # Connect logging signals
    service.status_updated.connect(lambda msg: logger.info(f"Status: {msg}"))
    service.error_occurred.connect(lambda msg: logger.error(f"Error: {msg}"))
    service.progress_updated.connect(lambda p: logger.debug(f"Progress: {p}%"))
    
    # Use complete metadata from load_nd2_metadata
    data_info = metadata.copy()
    data_info['pc_channel'] = pc_channel
    data_info['metadata'] = metadata  # Some services expect nested metadata
    
    # Process parameters
    params = {'mask_size': mask_size}
    
    # Use process_all_fovs with range support
    success = service.process_all_fovs(
        nd2_path=str(nd2_file),
        data_info=data_info,
        output_dir=output_dir,
        params=params,
        fov_start=fov_start,
        fov_end=fov_end
    )
    
    if success:
        logger.info(f"Binarization complete: All FOVs processed successfully")
    else:
        logger.error(f"Binarization failed")
        
    return success


def test_background_correction(
    nd2_file: Path,
    output_dir: Path,
    fov_start: int,
    fov_end: int,
    div_horiz: int = 7,
    div_vert: int = 5,
    fl_channel: int | None = None
) -> bool:
    """
    Test background correction on specified FOVs.
    
    Args:
        nd2_file: Path to ND2 file
        output_dir: Output directory  
        fov_start: Starting FOV index (inclusive)
        fov_end: Ending FOV index (inclusive)
        div_horiz: Horizontal divisions for background correction
        div_vert: Vertical divisions for background correction
        fl_channel: Fluorescence channel index (auto-detect if None)
    
    Returns:
        bool: True if successful
    """
    logger = logging.getLogger("test_background_correction")
    logger.info(f"Testing background correction on FOVs {fov_start}-{fov_end}")
    
    # First check if NPY files exist
    missing_npy = []
    for fov_idx in range(fov_start, fov_end + 1):
        fov_dir = output_dir / f"fov_{fov_idx:04d}"
        npy_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_fluorescence_raw.npy"
        if not npy_file.exists():
            missing_npy.append(fov_idx)
    
    if missing_npy:
        logger.error(f"Missing NPY files for FOVs: {missing_npy}")
        logger.error("Please run 'python test_modules.py copy' first to extract NPY files")
        return False
    
    # First check if binarization results exist for the range
    missing_binarization = []
    for fov_idx in range(fov_start, fov_end + 1):
        fov_dir = output_dir / f"fov_{fov_idx:04d}"
        binarized_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_binarized.npy"
        if not binarized_file.exists():
            missing_binarization.append(fov_idx)
    
    if missing_binarization:
        logger.error(f"Missing binarization results for FOVs: {missing_binarization}")
        logger.error("Please run 'python test_modules.py binarization' first")
        return False
    
    # Load metadata
    try:
        metadata = load_nd2_metadata(str(nd2_file))
        
        # Auto-detect fluorescence channel if not provided
        if fl_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'gfp' in channel.lower() or 'fluorescence' in channel.lower():
                    fl_channel = i
                    logger.info(f"Auto-detected fluorescence channel: {i} ({channel})")
                    break
            
            if fl_channel is None:
                logger.warning("Could not auto-detect fluorescence channel, using channel 1")
                fl_channel = 1 if len(metadata['channels']) > 1 else 0
                
    except Exception as e:
        logger.error(f"Failed to load ND2 metadata: {e}")
        return False
    
    # Create background correction service
    service = BackgroundCorrectionService()
    
    # Connect logging signals
    service.status_updated.connect(lambda msg: logger.info(f"Status: {msg}"))
    service.error_occurred.connect(lambda msg: logger.error(f"Error: {msg}"))
    service.progress_updated.connect(lambda p: logger.debug(f"Progress: {p}%"))
    
    # Use complete metadata from load_nd2_metadata
    data_info = metadata.copy()
    data_info['fl_channel'] = fl_channel
    data_info['metadata'] = metadata  # Some services expect nested metadata
    
    # Process parameters
    params = {
        'div_horiz': div_horiz,
        'div_vert': div_vert
    }
    
    # Use process_all_fovs with range support
    success = service.process_all_fovs(
        nd2_path=str(nd2_file),
        data_info=data_info,
        output_dir=output_dir,
        params=params,
        fov_start=fov_start,
        fov_end=fov_end
    )
    
    if success:
        logger.info(f"Background correction complete: All FOVs processed successfully")
    else:
        logger.error(f"Background correction failed")
        
    return success


def test_trace_extraction(
    nd2_file: Path,
    output_dir: Path,
    fov_start: int,
    fov_end: int,
    min_trace_length: int = 3
) -> bool:
    """
    Test trace extraction on specified FOVs.
    
    Args:
        nd2_file: Path to ND2 file
        output_dir: Output directory
        fov_start: Starting FOV index (inclusive)
        fov_end: Ending FOV index (inclusive)
        min_trace_length: Minimum trace length threshold
    
    Returns:
        bool: True if successful
    """
    logger = logging.getLogger("test_trace_extraction")
    logger.info(f"Testing trace extraction on FOVs {fov_start}-{fov_end}")
    
    # First check if required files exist for the range
    missing_deps = []
    for fov_idx in range(fov_start, fov_end + 1):
        fov_dir = output_dir / f"fov_{fov_idx:04d}"
        binarized_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_binarized.npy"
        corrected_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_fluorescence_corrected.npy"
        
        missing = []
        if not binarized_file.exists():
            missing.append("binarization")
        if not corrected_file.exists():
            missing.append("background correction")
            
        if missing:
            missing_deps.append((fov_idx, missing))
    
    if missing_deps:
        logger.error("Missing dependencies for FOVs:")
        for fov_idx, missing in missing_deps:
            logger.error(f"  FOV {fov_idx}: {', '.join(missing)}")
        logger.error("Please run the missing processing steps first:")
        logger.error("  1. python test_modules.py copy")
        logger.error("  2. python test_modules.py binarization")
        logger.error("  3. python test_modules.py background")
        return False
    
    # Load metadata
    try:
        metadata = load_nd2_metadata(str(nd2_file))
    except Exception as e:
        logger.error(f"Failed to load ND2 metadata: {e}")
        return False
    
    # Create trace extraction service
    service = TraceExtractionService()
    
    # Connect logging signals
    service.status_updated.connect(lambda msg: logger.info(f"Status: {msg}"))
    service.error_occurred.connect(lambda msg: logger.error(f"Error: {msg}"))
    service.progress_updated.connect(lambda p: logger.debug(f"Progress: {p}%"))
    
    # Use complete metadata from load_nd2_metadata
    data_info = metadata.copy()
    data_info['metadata'] = metadata  # Some services expect nested metadata
    
    # Process parameters
    params = {'min_trace_length': min_trace_length}
    
    # Use process_all_fovs with range support
    success = service.process_all_fovs(
        nd2_path=str(nd2_file),
        data_info=data_info,
        output_dir=output_dir,
        params=params,
        fov_start=fov_start,
        fov_end=fov_end
    )
    
    if success:
        logger.info(f"Trace extraction complete: All FOVs processed successfully")
        
        # Show summary for each FOV
        import pandas as pd
        for fov_idx in range(fov_start, fov_end + 1):
            traces_file = output_dir / f"fov_{fov_idx:04d}" / f"{nd2_file.stem}_fov{fov_idx:04d}_traces.csv"
            if traces_file.exists():
                try:
                    df = pd.read_csv(traces_file)
                    unique_cells = df['unique_cell_id'].nunique()
                    logger.info(f"  FOV {fov_idx}: {unique_cells} unique cells, {len(df)} total measurements")
                except Exception as e:
                    logger.warning(f"  Could not read trace summary for FOV {fov_idx}: {e}")
    else:
        logger.error(f"Trace extraction failed")
        
    return success


def test_copy_service(
    nd2_file: Path,
    output_dir: Path,
    fov_start: int,
    fov_end: int,
    pc_channel: int | None = None,
    fl_channel: int | None = None,
) -> bool:
    """
    Test copy service to extract NPY files from ND2.
    
    Args:
        nd2_file: Path to ND2 file
        output_dir: Output directory
        fov_start: Starting FOV index (inclusive)
        fov_end: Ending FOV index (inclusive)
        pc_channel: Phase contrast channel index (auto-detect if None)
        fl_channel: Fluorescence channel index (auto-detect if None)
        batch_size: Number of FOVs to process in parallel
    
    Returns:
        bool: True if successful
    """
    logger = logging.getLogger("test_copy_service")
    logger.info(f"Testing copy service on FOVs {fov_start}-{fov_end}")
    
    # Load metadata
    try:
        metadata = load_nd2_metadata(str(nd2_file))
        logger.info(f"Loaded ND2 file: {metadata['filename']}")
        logger.info(f"Channels: {metadata['channels']}")
        logger.info(f"FOVs: {metadata['n_fov']}")
        
        # Auto-detect channels if not provided
        if pc_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'phase' in channel.lower() or 'pc' in channel.lower():
                    pc_channel = i
                    logger.info(f"Auto-detected phase contrast channel: {i} ({channel})")
                    break
            if pc_channel is None:
                logger.warning("Could not auto-detect phase contrast channel, using channel 0")
                pc_channel = 0
                
        if fl_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'gfp' in channel.lower() or 'fluorescence' in channel.lower():
                    fl_channel = i
                    logger.info(f"Auto-detected fluorescence channel: {i} ({channel})")
                    break
                    
    except Exception as e:
        logger.error(f"Failed to load ND2 metadata: {e}")
        return False
    
    # Create copy service
    service = CopyService()
    
    # Connect logging signals
    service.status_updated.connect(lambda msg: logger.info(f"Status: {msg}"))
    service.error_occurred.connect(lambda msg: logger.error(f"Error: {msg}"))
    service.progress_updated.connect(lambda p: logger.debug(f"Progress: {p}%"))
    
    # Use complete metadata
    data_info = metadata.copy()
    data_info['pc_channel'] = pc_channel
    data_info['fl_channel'] = fl_channel
    data_info['metadata'] = metadata
    
    # Process parameters (copy service is now always sequential)
    params = {}
    
    # Process FOVs
    fov_indices = list(range(fov_start, fov_end + 1))
    success = service.process_batch(
        nd2_path=str(nd2_file),
        fov_indices=fov_indices,
        data_info=data_info,
        output_dir=output_dir,
        params=params
    )
    
    if success:
        logger.info(f"Copy service complete: All FOVs extracted successfully")
        
        # Check output files
        for fov_idx in fov_indices:
            fov_dir = output_dir / f"fov_{fov_idx:04d}"
            pc_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_phase_contrast_raw.npy"
            if pc_file.exists():
                logger.info(f"  FOV {fov_idx}: Phase contrast extracted ({pc_file.stat().st_size / 1e6:.1f} MB)")
            else:
                logger.warning(f"  FOV {fov_idx}: Phase contrast file missing")
                
            if fl_channel is not None:
                fl_file = fov_dir / f"{nd2_file.stem}_fov{fov_idx:04d}_fluorescence_raw.npy"
                if fl_file.exists():
                    logger.info(f"  FOV {fov_idx}: Fluorescence extracted ({fl_file.stat().st_size / 1e6:.1f} MB)")
    else:
        logger.error(f"Copy service failed")
        
    return success


def test_workflow(
    nd2_file: Path,
    output_dir: Path,
    fov_start: int,
    fov_end: int,
    mask_size: int = 3,
    div_horiz: int = 7,
    div_vert: int = 5,
    min_trace_length: int = 3,
    batch_size: int = 4,
    n_workers: int = 4,
    delete_raw: bool = False,
    pc_channel: int | None = None,
    fl_channel: int | None = None
) -> bool:
    """
    Test workflow on specified FOVs using parallel processing.
    
    Args:
        nd2_file: Path to ND2 file
        output_dir: Output directory
        fov_start: Starting FOV index (inclusive)
        fov_end: Ending FOV index (inclusive)
        mask_size: Mask size for binarization
        div_horiz: Horizontal divisions for background correction
        div_vert: Vertical divisions for background correction
        min_trace_length: Minimum trace length threshold
        batch_size: Number of FOVs to extract at once
        n_workers: Number of parallel workers
        delete_raw: Delete raw NPY files after processing
        pc_channel: Phase contrast channel index (auto-detect if None)
        fl_channel: Fluorescence channel index (auto-detect if None)
    
    Returns:
        bool: True if successful
    """
    logger = logging.getLogger("test_workflow")
    logger.info(f"Testing workflow on FOVs {fov_start}-{fov_end}")
    logger.info(f"Batch size: {batch_size}, Workers: {n_workers}")
    
    # Load metadata
    try:
        metadata = load_nd2_metadata(str(nd2_file))
        logger.info(f"Loaded ND2 file: {metadata['filename']}")
        logger.info(f"Channels: {metadata['channels']}")
        logger.info(f"FOVs: {metadata['n_fov']}")
        
        # Auto-detect channels if not provided
        if pc_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'phase' in channel.lower() or 'pc' in channel.lower():
                    pc_channel = i
                    logger.info(f"Auto-detected phase contrast channel: {i} ({channel})")
                    break
            if pc_channel is None:
                logger.warning("Could not auto-detect phase contrast channel, using channel 0")
                pc_channel = 0
                
        if fl_channel is None:
            for i, channel in enumerate(metadata['channels']):
                if 'gfp' in channel.lower() or 'fluorescence' in channel.lower():
                    fl_channel = i
                    logger.info(f"Auto-detected fluorescence channel: {i} ({channel})")
                    break
            if fl_channel is None:
                logger.warning("Could not auto-detect fluorescence channel, using channel 1")
                fl_channel = 1 if len(metadata['channels']) > 1 else 0
                
    except Exception as e:
        logger.error(f"Failed to load ND2 metadata: {e}")
        return False
    
    # Create workflow coordinator
    coordinator = WorkflowCoordinator()
    
    # Connect logging signals
    coordinator.status_updated.connect(lambda msg: logger.info(f"Status: {msg}"))
    coordinator.error_occurred.connect(lambda msg: logger.error(f"Error: {msg}"))
    coordinator.progress_updated.connect(lambda p: logger.info(f"Overall Progress: {p}%"))
    
    # Also connect copy service signals
    coordinator.copy_service.status_updated.connect(lambda msg: logger.info(f"[Copy] {msg}"))
    coordinator.copy_service.error_occurred.connect(lambda msg: logger.error(f"[Copy] {msg}"))
    
    # Use complete metadata
    data_info = metadata.copy()
    data_info['pc_channel'] = pc_channel
    data_info['fl_channel'] = fl_channel
    data_info['metadata'] = metadata
    
    # Process parameters
    params = {
        'mask_size': mask_size,
        'div_horiz': div_horiz,
        'div_vert': div_vert,
        'min_trace_length': min_trace_length,
        'delete_raw_after_processing': delete_raw
    }
    
    # Run parallel workflow
    import time
    start_time = time.time()
    
    success = coordinator.run_complete_workflow(
        nd2_path=str(nd2_file),
        data_info=data_info,
        output_dir=output_dir,
        params=params,
        fov_start=fov_start,
        fov_end=fov_end,
        batch_size=batch_size,
        n_workers=n_workers
    )
    
    elapsed_time = time.time() - start_time
    
    if success:
        logger.info(f"Workflow completed in {elapsed_time:.1f} seconds")
        
        # Show summary
        completed_count = 0
        for fov_idx in range(fov_start, fov_end + 1):
            traces_file = output_dir / f"fov_{fov_idx:04d}" / f"{nd2_file.stem}_fov{fov_idx:04d}_traces.csv"
            if traces_file.exists():
                completed_count += 1
                
        logger.info(f"Successfully processed {completed_count}/{fov_end - fov_start + 1} FOVs")
    else:
        logger.error(f"Workflow failed after {elapsed_time:.1f} seconds")
        
    return success


def main():
    """Main entry point for module testing."""
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description="Test PyAMA-Qt processing modules",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test individual modules in order (single-threaded):
  python test_modules.py copy          # 1. Extract NPY files from ND2
  python test_modules.py binarization  # 2. Run binarization (requires NPY files)
  python test_modules.py background    # 3. Run background correction (requires NPY + binarization)
  python test_modules.py traces        # 4. Extract traces (requires all previous steps)
  
  # Or test complete workflow with parallel processing:
  python test_modules.py workflow -v   # Run all steps with multiprocessing
  
Note: Edit the constants at the top of this script to configure test parameters."""
    )
    
    parser.add_argument(
        "module",
        choices=["copy", "binarization", "background", "traces", "workflow"],
        help="Module to test"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=VERBOSE,
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    setup_logging(args.verbose)
    
    # Validate configuration
    if not ND2_FILE.exists():
        print(f"Error: ND2 file not found: {ND2_FILE}")
        print("Please update the ND2_FILE constant at the top of this script")
        return 1
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Run appropriate test
    success = False
    module = args.module
    
    if module == 'copy':
        success = test_copy_service(
            ND2_FILE,
            OUTPUT_DIR,
            FOV_START,
            FOV_END,
            PC_CHANNEL,
            FL_CHANNEL,
        )
    
    elif module == 'binarization':
        success = test_binarization(
            ND2_FILE,
            OUTPUT_DIR,
            FOV_START,
            FOV_END,
            MASK_SIZE,
            PC_CHANNEL
        )
    
    elif module == 'background':
        success = test_background_correction(
            ND2_FILE,
            OUTPUT_DIR,
            FOV_START,
            FOV_END,
            DIV_HORIZ,
            DIV_VERT,
            FL_CHANNEL
        )
    
    elif module == 'traces':
        success = test_trace_extraction(
            ND2_FILE,
            OUTPUT_DIR,
            FOV_START,
            FOV_END,
            MIN_TRACE_LENGTH
        )
    
    elif module == 'workflow':
        success = test_workflow(
            ND2_FILE,
            OUTPUT_DIR,
            FOV_START,
            FOV_END,
            MASK_SIZE,
            DIV_HORIZ,
            DIV_VERT,
            MIN_TRACE_LENGTH,
            BATCH_SIZE,
            N_WORKERS,
            DELETE_RAW,
            PC_CHANNEL,
            FL_CHANNEL
        )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
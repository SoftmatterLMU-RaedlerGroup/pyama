#!/usr/bin/env python3
"""
Command-line interface for PyAMA-Qt microscopy image analysis.

This CLI allows running the complete processing pipeline on servers
or for batch processing without the GUI.
"""

import argparse
import sys
import logging
from pathlib import Path
import numpy as np
from nd2reader import ND2Reader

# Import services without GUI dependencies
from .services.workflow import WorkflowCoordinator


def setup_logging(log_level: str = "INFO", log_file: Path | None = None):
    """Set up logging configuration."""
    level = getattr(logging, log_level.upper())
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Set up root logger
    logger = logging.getLogger()
    logger.setLevel(level)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)


def load_nd2_metadata(nd2_path: str) -> dict[str, object]:
    """Load ND2 file metadata without GUI dependencies."""
    try:
        with ND2Reader(nd2_path) as images:
            # Get basic metadata
            metadata = {
                'n_frames': len(images.metadata['t_coordinates']) if 't_coordinates' in images.metadata else 1,
                'n_fov': len(images.metadata['fields_of_view']) if 'fields_of_view' in images.metadata else 1,
                'height': images.metadata['height'],
                'width': images.metadata['width'],
                'channels': list(images.metadata['channels']) if 'channels' in images.metadata else ['Unknown'],
                'n_channels': len(images.metadata['channels']) if 'channels' in images.metadata else 1
            }
            
            # Find phase contrast and fluorescence channels
            channels = metadata['channels']
            pc_channel = None
            fl_channel = None
            
            # Try to identify channels by name
            for i, channel in enumerate(channels):
                channel_lower = channel.lower()
                if 'phase' in channel_lower or 'pc' in channel_lower or 'ph' in channel_lower:
                    pc_channel = i
                elif 'gfp' in channel_lower or 'fluor' in channel_lower or 'green' in channel_lower:
                    fl_channel = i
            
            # Fallback: assume first channel is phase contrast, second is fluorescence
            if pc_channel is None:
                pc_channel = 0
            if fl_channel is None and metadata['n_channels'] > 1:
                fl_channel = 1
            elif fl_channel is None:
                fl_channel = 0  # Use same channel if only one available
            
            return {
                'filename': Path(nd2_path).name,
                'metadata': metadata,
                'pc_channel': pc_channel,
                'fl_channel': fl_channel
            }
            
    except Exception as e:
        raise RuntimeError(f"Failed to load ND2 metadata: {str(e)}")


class CLIWorkflowCoordinator:
    """CLI-adapted workflow coordinator that reuses existing workflow logic."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        
    def run_workflow(self, nd2_path: str, output_dir: Path, params: dict[str, object]) -> bool:
        """Run the complete workflow with CLI logging."""
        try:
            self.logger.info(f"Starting PyAMA-Qt processing pipeline")
            self.logger.info(f"Input file: {nd2_path}")
            self.logger.info(f"Output directory: {output_dir}")
            
            # Load metadata
            self.logger.info("Loading ND2 metadata...")
            data_info = load_nd2_metadata(nd2_path)
            
            # Override channel detection if specified in params
            if 'pc_channel' in params:
                data_info['pc_channel'] = params['pc_channel']
            if 'fl_channel' in params:
                data_info['fl_channel'] = params['fl_channel']
            
            metadata = data_info['metadata']
            self.logger.info(f"Found {metadata['n_fov']} FOVs, {metadata['n_frames']} frames")
            self.logger.info(f"Image size: {metadata['height']}x{metadata['width']}")
            self.logger.info(f"Channels: {metadata['channels']}")
            self.logger.info(f"Using PC channel: {data_info['pc_channel']}, FL channel: {data_info['fl_channel']}")
            
            # Create workflow coordinator (reuse existing logic)
            workflow = CLIWorkflowWrapper()
            
            # Run the workflow
            success = workflow.run_complete_workflow(nd2_path, data_info, output_dir, params)
            
            if success:
                self.logger.info("Pipeline completed successfully!")
                return True
            else:
                self.logger.error("Pipeline failed!")
                return False
                
        except Exception as e:
            self.logger.error(f"Pipeline error: {str(e)}")
            return False


class CLIWorkflowWrapper(WorkflowCoordinator):
    """CLI wrapper that extends existing WorkflowCoordinator for headless operation."""
    
    def __init__(self):
        # Initialize without Qt parent for CLI operation
        super().__init__(parent=None)
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Connect all services to CLI logging
        for service in self.get_all_services():
            service.status_updated.connect(self._log_status)
            service.error_occurred.connect(self._log_error)
    
    def _log_status(self, message: str):
        """Log status updates from services."""
        self.logger.info(message)
    
    def _log_error(self, message: str):
        """Log error messages from services."""
        self.logger.error(message)


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="PyAMA-Qt: Microscopy Image Analysis Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s data.nd2 -o results/
  %(prog)s data.nd2 -o results/ --mask-size 5 --min-trace-length 5
  %(prog)s data.nd2 -o results/ --pc-channel 0 --fl-channel 1 --log-level DEBUG
        """
    )
    
    # Required arguments
    parser.add_argument('nd2_file', type=str, help='Path to ND2 input file')
    parser.add_argument('-o', '--output', type=str, required=True,
                       help='Output directory for results')
    
    # Processing parameters
    parser.add_argument('--mask-size', type=int, default=3,
                       help='Mask size for binarization (default: 3)')
    parser.add_argument('--div-horiz', type=int, default=7,
                       help='Horizontal divisions for background correction (default: 7)')
    parser.add_argument('--div-vert', type=int, default=5,
                       help='Vertical divisions for background correction (default: 5)')
    parser.add_argument('--min-trace-length', type=int, default=3,
                       help='Minimum trace length to keep (default: 3)')
    
    # Channel selection
    parser.add_argument('--pc-channel', type=int, default=None,
                       help='Phase contrast channel index (auto-detected if not specified)')
    parser.add_argument('--fl-channel', type=int, default=None,
                       help='Fluorescence channel index (auto-detected if not specified)')
    
    # Logging options
    parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
                       default='INFO', help='Logging level (default: INFO)')
    parser.add_argument('--log-file', type=str, default=None,
                       help='Log file path (logs to console if not specified)')
    
    args = parser.parse_args()
    
    # Validate inputs
    nd2_path = Path(args.nd2_file)
    if not nd2_path.exists():
        print(f"Error: ND2 file not found: {nd2_path}")
        sys.exit(1)
    
    output_dir = Path(args.output)
    
    # Set up logging
    log_file = Path(args.log_file) if args.log_file else None
    setup_logging(args.log_level, log_file)
    
    # Build parameters dict
    params = {
        'mask_size': args.mask_size,
        'div_horiz': args.div_horiz,
        'div_vert': args.div_vert,
        'min_trace_length': args.min_trace_length,
    }
    
    # Override channel detection if specified
    if args.pc_channel is not None:
        params['pc_channel'] = args.pc_channel
    if args.fl_channel is not None:
        params['fl_channel'] = args.fl_channel
    
    # Run the workflow
    coordinator = CLIWorkflowCoordinator()
    success = coordinator.run_workflow(str(nd2_path), output_dir, params)
    
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
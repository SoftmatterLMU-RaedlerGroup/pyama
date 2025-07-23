#!/usr/bin/env python3
"""
Example script for testing binarization algorithms on single TIFF frames.

Usage:
    python test_binarization.py path/to/your/test_frame.tif
"""

import sys
from pathlib import Path

# Add src to path so we can import pyama_qt modules
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import binarization testing utilities from same directory
from utils import (
    test_binarization_methods, 
    quick_test_frame,
    example_parameter_sweep
)
from pyama_qt.utils.binarization import BinarizationMethod


def main():
    if len(sys.argv) != 2:
        print("Usage: python tests/binarization/main.py <path_to_test_image>")
        print("\nExample:")
        print("  python tests/binarization/main.py test_data/phase_contrast_frame.tif")
        return
    
    image_path = sys.argv[1]
    
    if not Path(image_path).exists():
        print(f"Error: Image file not found: {image_path}")
        return
    
    print(f"Testing binarization methods on: {image_path}")
    print("=" * 60)
    
    # Quick test with logarithmic standard deviation (default for phase contrast)
    print("\n1. Quick test with logarithmic standard deviation method:")
    original, binary = quick_test_frame(
        image_path, 
        mask_size=3, 
        method=BinarizationMethod.LOGARITHMIC_STD,
        show_plot=False  # Set to True if you want to see plots
    )
    
    print(f"   Original shape: {original.shape}")
    print(f"   Binary result: {binary.sum()} foreground pixels ({binary.mean():.1%})")
    
    # Test all available methods
    print("\n2. Testing all binarization methods:")
    results = test_binarization_methods(
        image_path,
        mask_size=3,
        save_results=True
    )
    
    print(f"   Saved comparison plots to: {Path(image_path).parent}")
    
    # Parameter sweep example
    print("\n3. Parameter sweep for logarithmic standard deviation:")
    param_results = example_parameter_sweep(
        image_path,
        method=BinarizationMethod.LOGARITHMIC_STD
    )
    
    print(f"   Tested mask sizes: {list(range(3, 10, 2))}")
    print(f"   Parameter sweep plots saved to: {Path(image_path).parent / 'parameter_sweep'}")
    
    # Show method-specific recommendations
    print("\n4. Recommendations:")
    print("   - For phase contrast microscopy: Use 'log_std' (logarithmic standard deviation)")
    print("   - For fluorescence microscopy: Try 'adaptive' or 'local' methods")
    print("   - For high-contrast images: 'otsu' may work well")
    print("   - For edge-rich images: Try 'edge' method")
    
    print(f"\nDone! Check the output directory for visualization results.")


if __name__ == "__main__":
    main()
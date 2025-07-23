"""
Testing utilities for binarization algorithm evaluation and comparison.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from pyama_qt.utils.binarization import compare_binarization_methods, BinarizationMethod


def load_test_frame(image_path: str) -> np.ndarray:
    """
    Load a single frame from TIFF or other image format for testing.
    
    Args:
        image_path: Path to the test image file
        
    Returns:
        np.ndarray: Loaded image as numpy array
    """
    image_path = Path(image_path)
    
    if not image_path.exists():
        raise FileNotFoundError(f"Test image not found: {image_path}")
    
    # Load image using PIL for broader format support
    with Image.open(image_path) as img:
        # Convert to numpy array
        frame = np.array(img)
        
        # Handle different image modes
        if len(frame.shape) == 3:
            # If RGB, convert to grayscale
            if frame.shape[2] == 3:
                frame = np.mean(frame, axis=2)
            elif frame.shape[2] == 4:  # RGBA
                frame = np.mean(frame[:, :, :3], axis=2)
    
    return frame.astype(np.float64)


def test_binarization_methods(image_path: str, mask_size: int = 3, 
                            methods: Optional[List[BinarizationMethod]] = None,
                            save_results: bool = True,
                            output_dir: Optional[str] = None,
                            **kwargs) -> Dict[str, np.ndarray]:
    """
    Test multiple binarization methods on a single test frame.
    
    Args:
        image_path: Path to test image (TIFF, PNG, etc.)
        mask_size: Size parameter for morphological operations
        methods: List of methods to test (None = all methods)
        save_results: Whether to save comparison plots
        output_dir: Directory to save results (None = same as input image)
        **kwargs: Additional parameters for binarization methods
        
    Returns:
        Dict[str, np.ndarray]: Dictionary mapping method names to binary results
    """
    # Load test frame
    frame = load_test_frame(image_path)
    
    # Test binarization methods
    results = compare_binarization_methods(frame, mask_size, methods, **kwargs)
    
    # Create comparison visualization
    if save_results:
        save_binarization_comparison(frame, results, image_path, output_dir)
    
    return results


def save_binarization_comparison(original_frame: np.ndarray, 
                               results: Dict[str, np.ndarray],
                               original_path: str,
                               output_dir: Optional[str] = None):
    """
    Save a comparison plot of different binarization methods.
    
    Args:
        original_frame: Original input frame
        results: Dictionary of binarization results
        original_path: Path to original image (for naming output)
        output_dir: Directory to save comparison (None = same as input)
    """
    if output_dir is None:
        output_dir = Path(original_path).parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create comparison plot
    n_methods = len(results)
    n_cols = min(3, n_methods + 1)  # +1 for original
    n_rows = (n_methods + 1 + n_cols - 1) // n_cols  # Ceiling division
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(4*n_cols, 4*n_rows))
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    elif n_cols == 1:
        axes = axes.reshape(-1, 1)
    
    # Flatten axes for easy indexing
    axes_flat = axes.flatten()
    
    # Show original image
    axes_flat[0].imshow(original_frame, cmap='gray')
    axes_flat[0].set_title('Original')
    axes_flat[0].axis('off')
    
    # Show binarization results
    for i, (method_name, binary_result) in enumerate(results.items(), 1):
        if i < len(axes_flat):
            axes_flat[i].imshow(binary_result, cmap='gray')
            axes_flat[i].set_title(f'{method_name.replace("_", " ").title()}')
            axes_flat[i].axis('off')
    
    # Hide unused subplots
    for i in range(len(results) + 1, len(axes_flat)):
        axes_flat[i].axis('off')
    
    plt.tight_layout()
    
    # Save comparison plot
    base_name = Path(original_path).stem
    output_path = output_dir / f"{base_name}_binarization_comparison.png"
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    plt.close()
    
    print(f"Comparison saved to: {output_path}")
    
    # Also save individual results
    for method_name, binary_result in results.items():
        result_path = output_dir / f"{base_name}_{method_name}_binary.png"
        plt.figure(figsize=(8, 8))
        plt.imshow(binary_result, cmap='gray')
        plt.title(f'{method_name.replace("_", " ").title()} Binarization')
        plt.axis('off')
        plt.savefig(result_path, dpi=150, bbox_inches='tight')
        plt.close()


def analyze_binarization_stats(results: Dict[str, np.ndarray]) -> Dict[str, Dict[str, float]]:
    """
    Analyze statistics of different binarization results.
    
    Args:
        results: Dictionary of binarization results
        
    Returns:
        Dict[str, Dict[str, float]]: Statistics for each method
    """
    stats = {}
    
    for method_name, binary_result in results.items():
        total_pixels = binary_result.size
        foreground_pixels = np.sum(binary_result)
        background_pixels = total_pixels - foreground_pixels
        
        stats[method_name] = {
            'foreground_fraction': foreground_pixels / total_pixels,
            'background_fraction': background_pixels / total_pixels,
            'foreground_pixels': int(foreground_pixels),
            'background_pixels': int(background_pixels),
            'total_pixels': int(total_pixels)
        }
    
    return stats


def print_binarization_stats(stats: Dict[str, Dict[str, float]]):
    """
    Print binarization statistics in a readable format.
    
    Args:
        stats: Statistics dictionary from analyze_binarization_stats
    """
    print("\nBinarization Method Statistics:")
    print("=" * 50)
    
    for method_name, method_stats in stats.items():
        print(f"\n{method_name.replace('_', ' ').title()}:")
        print(f"  Foreground: {method_stats['foreground_pixels']:,} pixels ({method_stats['foreground_fraction']:.1%})")
        print(f"  Background: {method_stats['background_pixels']:,} pixels ({method_stats['background_fraction']:.1%})")


def quick_test_frame(image_path: str, mask_size: int = 3, 
                    method: BinarizationMethod = BinarizationMethod.LOGARITHMIC_STD,
                    show_plot: bool = True, **kwargs) -> Tuple[np.ndarray, np.ndarray]:
    """
    Quick test of a single binarization method on a frame.
    
    Args:
        image_path: Path to test image
        mask_size: Size parameter for morphological operations
        method: Binarization method to test
        show_plot: Whether to display comparison plot
        **kwargs: Additional parameters for binarization method
        
    Returns:
        Tuple[np.ndarray, np.ndarray]: (original_frame, binary_result)
    """
    from pyama_qt.utils.binarization import get_binarization_function
    
    # Load frame
    frame = load_test_frame(image_path)
    
    # Apply binarization
    binarization_func = get_binarization_function(method)
    binary_result = binarization_func(frame, mask_size, **kwargs)
    
    # Show comparison if requested
    if show_plot:
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        ax1.imshow(frame, cmap='gray')
        ax1.set_title('Original')
        ax1.axis('off')
        
        ax2.imshow(binary_result, cmap='gray')
        ax2.set_title(f'{method.value.replace("_", " ").title()} Binarization')
        ax2.axis('off')
        
        plt.tight_layout()
        plt.show()
    
    return frame, binary_result


# Example usage functions
def example_test_phase_contrast(image_path: str):
    """
    Example: Test binarization methods optimized for phase contrast microscopy.
    
    Args:
        image_path: Path to phase contrast test image
    """
    # Methods particularly good for phase contrast
    phase_contrast_methods = [
        BinarizationMethod.LOGARITHMIC_STD,
        BinarizationMethod.EDGE_BASED,
        BinarizationMethod.ADAPTIVE_THRESHOLD,
        BinarizationMethod.LOCAL_THRESHOLD
    ]
    
    print(f"Testing phase contrast binarization methods on: {image_path}")
    
    results = test_binarization_methods(
        image_path, 
        mask_size=3,
        methods=phase_contrast_methods,
        save_results=True
    )
    
    # Analyze and print statistics
    stats = analyze_binarization_stats(results)
    print_binarization_stats(stats)
    
    return results


def example_parameter_sweep(image_path: str, method: BinarizationMethod = BinarizationMethod.LOGARITHMIC_STD):
    """
    Example: Test different parameter values for a specific method.
    
    Args:
        image_path: Path to test image
        method: Binarization method to test
    """
    print(f"Parameter sweep for {method.value} on: {image_path}")
    
    # Test different mask sizes
    mask_sizes = [3, 5, 7, 9]
    results = {}
    
    for mask_size in mask_sizes:
        frame, binary_result = quick_test_frame(
            image_path, 
            mask_size=mask_size, 
            method=method,
            show_plot=False
        )
        results[f"mask_size_{mask_size}"] = binary_result
    
    # Save comparison
    output_dir = Path(image_path).parent / "parameter_sweep"
    save_binarization_comparison(frame, results, image_path, output_dir)
    
    # Print statistics
    stats = analyze_binarization_stats(results)
    print_binarization_stats(stats)
    
    return results
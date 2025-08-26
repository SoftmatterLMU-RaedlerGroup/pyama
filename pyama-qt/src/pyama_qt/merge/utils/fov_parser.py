"""FOV range parsing utilities for the merge module.

This module provides functions to parse FOV range notation (e.g., "1-4,6,9-20")
and validate against available FOV indices using 0-based indexing.
"""

import re
from typing import List, Set, Tuple


def parse_fov_ranges(range_str: str) -> List[int]:
    """Parse FOV range notation into a list of FOV indices.
    
    Supports:
    - Individual FOVs: "1,3,5" -> [1, 3, 5]
    - Ranges: "1-5" -> [1, 2, 3, 4, 5]
    - Mixed notation: "1-4,6,9-20" -> [1, 2, 3, 4, 6, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
    
    Args:
        range_str: String containing FOV range notation
        
    Returns:
        List of FOV indices (0-based)
        
    Raises:
        ValueError: If the range string format is invalid
    """
    if not range_str or not range_str.strip():
        return []
    
    # Remove whitespace
    range_str = range_str.strip()
    
    # Split by commas to get individual parts
    parts = [part.strip() for part in range_str.split(',')]
    fov_indices = set()
    
    for part in parts:
        if not part:
            continue
            
        # Check if it's a range (contains hyphen)
        if '-' in part:
            range_match = re.match(r'^(\d+)-(\d+)$', part)
            if not range_match:
                raise ValueError(f"Invalid range format: '{part}'. Expected format: 'start-end'")
            
            start, end = map(int, range_match.groups())
            if start > end:
                raise ValueError(f"Invalid range: '{part}'. Start index must be <= end index")
            
            # Add all indices in the range (inclusive)
            fov_indices.update(range(start, end + 1))
        else:
            # Single FOV index
            if not re.match(r'^\d+$', part):
                raise ValueError(f"Invalid FOV index: '{part}'. Must be a non-negative integer")
            
            fov_indices.add(int(part))
    
    return sorted(list(fov_indices))


def validate_fov_ranges(range_str: str, available_fovs: List[int]) -> Tuple[bool, List[str]]:
    """Validate FOV range notation against available FOV indices.
    
    Args:
        range_str: String containing FOV range notation
        available_fovs: List of available FOV indices (0-based)
        
    Returns:
        Tuple of (is_valid, error_messages)
        - is_valid: True if all specified FOVs are available
        - error_messages: List of error messages if validation fails
    """
    errors = []
    
    try:
        requested_fovs = parse_fov_ranges(range_str)
    except ValueError as e:
        return False, [str(e)]
    
    if not requested_fovs:
        return True, []  # Empty range is valid
    
    available_set = set(available_fovs)
    requested_set = set(requested_fovs)
    
    # Check for FOVs that don't exist
    missing_fovs = requested_set - available_set
    if missing_fovs:
        missing_sorted = sorted(list(missing_fovs))
        errors.append(f"FOV indices not available: {missing_sorted}")
    
    return len(errors) == 0, errors


def get_fov_range_summary(range_str: str, available_fovs: List[int]) -> dict:
    """Get a summary of FOV range parsing results.
    
    Args:
        range_str: String containing FOV range notation
        available_fovs: List of available FOV indices (0-based)
        
    Returns:
        Dictionary containing:
        - 'valid': bool indicating if the range is valid
        - 'resolved_fovs': list of resolved FOV indices
        - 'count': number of resolved FOVs
        - 'errors': list of error messages
    """
    is_valid, errors = validate_fov_ranges(range_str, available_fovs)
    
    try:
        resolved_fovs = parse_fov_ranges(range_str) if is_valid else []
    except ValueError:
        resolved_fovs = []
    
    return {
        'valid': is_valid,
        'resolved_fovs': resolved_fovs,
        'count': len(resolved_fovs),
        'errors': errors
    }


def check_fov_conflicts(sample_ranges: List[Tuple[str, str]], available_fovs: List[int]) -> List[str]:
    """Check for conflicts between sample FOV assignments.
    
    Args:
        sample_ranges: List of (sample_name, range_str) tuples
        available_fovs: List of available FOV indices (0-based)
        
    Returns:
        List of conflict error messages
    """
    errors = []
    all_assigned_fovs = {}  # fov_index -> sample_name
    
    for sample_name, range_str in sample_ranges:
        if not range_str or not range_str.strip():
            continue
            
        try:
            fov_indices = parse_fov_ranges(range_str)
        except ValueError as e:
            errors.append(f"Sample '{sample_name}': {e}")
            continue
        
        # Check for conflicts with previously assigned FOVs
        for fov_idx in fov_indices:
            if fov_idx in all_assigned_fovs:
                other_sample = all_assigned_fovs[fov_idx]
                errors.append(f"FOV {fov_idx} assigned to both '{sample_name}' and '{other_sample}'")
            else:
                all_assigned_fovs[fov_idx] = sample_name
    
    return errors
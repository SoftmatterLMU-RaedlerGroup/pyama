"""
Latin Hypercube Sampling for multi-start optimization.

Provides efficient sampling of parameter space for robust optimization.
"""

import numpy as np
from typing import Dict, Tuple, List


def latin_hypercube_sample(
    bounds: Dict[str, Tuple[float, float]], n_samples: int, seed: int | None = None
) -> List[Dict[str, float]]:
    """
    Generate Latin Hypercube samples for parameter initialization.

    Latin Hypercube Sampling ensures efficient coverage of parameter space
    by dividing each parameter dimension into equally-spaced intervals.

    Args:
        bounds: Dictionary of parameter bounds {param_name: (min, max)}
        n_samples: Number of samples to generate
        seed: Random seed for reproducibility

    Returns:
        List of parameter dictionaries for initialization
    """
    if seed is not None:
        np.random.seed(seed)

    param_names = list(bounds.keys())
    n_params = len(param_names)

    if n_samples <= 0:
        return []

    # Generate LHS samples in [0, 1] space
    samples = np.zeros((n_samples, n_params))

    for i in range(n_params):
        # Create equally-spaced intervals
        intervals = np.arange(n_samples) / n_samples

        # Add random offset within each interval
        intervals += np.random.random(n_samples) / n_samples

        # Shuffle to break correlation between dimensions
        np.random.shuffle(intervals)

        samples[:, i] = intervals

    # Transform from [0, 1] to actual parameter bounds
    sample_dicts = []
    for sample in samples:
        param_dict = {}
        for i, param_name in enumerate(param_names):
            min_val, max_val = bounds[param_name]

            # Handle logarithmic parameters (large ranges)
            if max_val / min_val > 1000 and min_val > 0:
                # Use log-uniform distribution for large ranges
                log_min = np.log10(min_val)
                log_max = np.log10(max_val)
                log_val = log_min + sample[i] * (log_max - log_min)
                param_dict[param_name] = 10**log_val
            else:
                # Linear scaling for normal ranges
                param_dict[param_name] = min_val + sample[i] * (max_val - min_val)

        sample_dicts.append(param_dict)

    return sample_dicts


def add_noise_to_sample(
    base_params: Dict[str, float],
    bounds: Dict[str, Tuple[float, float]],
    noise_level: float = 0.1,
    seed: int | None = None,
) -> Dict[str, float]:
    """
    Add random noise to parameter values for additional starts.

    Args:
        base_params: Base parameter values
        bounds: Parameter bounds for clipping
        noise_level: Relative noise level (0.1 = 10%)
        seed: Random seed for reproducibility

    Returns:
        Noisy parameter dictionary
    """
    if seed is not None:
        np.random.seed(seed)

    noisy_params = {}

    for param_name, base_value in base_params.items():
        if param_name not in bounds:
            noisy_params[param_name] = base_value
            continue

        min_val, max_val = bounds[param_name]

        # Add relative noise
        noise = np.random.normal(0, noise_level * abs(base_value))
        noisy_value = base_value + noise

        # Clip to bounds
        noisy_value = np.clip(noisy_value, min_val, max_val)

        noisy_params[param_name] = noisy_value

    return noisy_params


def generate_multistart_params(
    bounds: Dict[str, Tuple[float, float]],
    default_params: Dict[str, float],
    n_starts: int,
    noise_level: float = 0.1,
    seed: int | None = None,
) -> List[Dict[str, float]]:
    """
    Generate multiple starting parameter sets for robust optimization.

    Combines Latin Hypercube Sampling with noise-perturbed defaults.

    Args:
        bounds: Parameter bounds
        default_params: Default parameter values
        n_starts: Number of starting parameter sets
        noise_level: Noise level for perturbing defaults
        seed: Random seed for reproducibility

    Returns:
        List of parameter dictionaries for multi-start optimization
    """
    if n_starts <= 0:
        return []

    if seed is not None:
        np.random.seed(seed)

    param_sets = []

    if n_starts == 1:
        # Single start: use defaults
        param_sets.append(default_params.copy())
    else:
        # First start: use defaults
        param_sets.append(default_params.copy())

        if n_starts == 2:
            # Second start: add noise to defaults
            noisy_params = add_noise_to_sample(
                default_params, bounds, noise_level, seed=seed
            )
            param_sets.append(noisy_params)
        else:
            # Multiple starts: mix of LHS and noisy defaults
            n_lhs = max(1, n_starts - 2)  # Reserve 2 slots for defaults

            # Generate LHS samples
            lhs_samples = latin_hypercube_sample(bounds, n_lhs, seed=seed)
            param_sets.extend(lhs_samples)

            # Add one more noisy default if we have room
            if len(param_sets) < n_starts:
                noisy_params = add_noise_to_sample(
                    default_params, bounds, noise_level, seed=seed + 1
                )
                param_sets.append(noisy_params)

    return param_sets[:n_starts]

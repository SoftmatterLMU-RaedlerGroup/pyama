"""Main CLI application for pyama-air."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import typer
import yaml

from pyama_core.io import load_microscopy_file
from pyama_core.processing.extraction.features import (
    list_fluorescence_features,
    list_phase_features,
)
from pyama_core.processing.merge import (
    parse_fov_range,
    run_merge as run_core_merge,
)
from pyama_core.processing.workflow.run import run_complete_workflow
from pyama_core.types.processing import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)


def cli_app() -> None:
    """Interactive CLI for PyAMA workflows and merging."""
    typer.echo("Welcome to PyAMA-Air CLI!")
    typer.echo("")

    while True:
        typer.echo("Select an option:")
        typer.echo("1. Workflow - Run PyAMA processing workflow")
        typer.echo("2. Merge - Merge CSV outputs from multiple samples")
        typer.echo("3. Exit")
        typer.echo("")

        choice = typer.prompt("Enter your choice (1-3)", default="1").strip()

        if choice == "1":
            workflow()
            break
        elif choice == "2":
            merge()
            break
        elif choice == "3":
            typer.echo("Goodbye!")
            break
        else:
            typer.secho("Invalid choice. Please enter 1, 2, or 3.", fg=typer.colors.RED)
            typer.echo("")


# Dynamic feature discovery - will be populated at runtime
PC_FEATURE_OPTIONS: list[str] = []
FL_FEATURE_OPTIONS: list[str] = []


def _prompt_nd2_path() -> Path:
    """Prompt until the user provides an ND2 path that exists."""
    while True:
        raw_path = typer.prompt("Enter the path to your ND2 file").strip()
        if not raw_path:
            typer.secho(
                "Please provide a non-empty path.", err=True, fg=typer.colors.RED
            )
            continue
        nd2_path = Path(raw_path).expanduser()
        if not nd2_path.exists():
            typer.secho(
                f"Path '{nd2_path}' does not exist.", err=True, fg=typer.colors.RED
            )
            continue
        if not nd2_path.is_file():
            typer.secho(
                f"Path '{nd2_path}' is not a file.", err=True, fg=typer.colors.RED
            )
            continue
        return nd2_path


def _prompt_channel(prompt_text: str, valid_indices: Iterable[int]) -> int:
    """Prompt for a channel index until a valid selection is made."""
    valid_set = set(valid_indices)
    while True:
        value = typer.prompt(prompt_text).strip()
        try:
            selection = int(value)
        except ValueError:
            typer.secho(
                "Please enter a numeric channel index.", err=True, fg=typer.colors.RED
            )
            continue
        if selection not in valid_set:
            typer.secho(
                f"Channel {selection} is not in the available list: {sorted(valid_set)}",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return selection


def _prompt_features(channel_label: str, options: list[str]) -> list[str]:
    """Prompt for a set of features given a list of available options."""
    selected: list[str] = []
    for feature in options:
        if typer.confirm(f"Enable '{feature}' for {channel_label}?", default=True):
            selected.append(feature)
    return selected


def _print_channel_summary(channel_names: list[str]) -> None:
    typer.echo("")
    typer.secho("Discovered channels:", bold=True)
    for idx, name in enumerate(channel_names):
        label = name if name else f"C{idx}"
        typer.echo(f"  [{idx}] {label}")
    typer.echo("")


def _prompt_fovs_for_sample(sample_name: str) -> str:
    """Prompt for a valid FOV specification."""
    while True:
        fovs_input = typer.prompt(
            f"FOVs for '{sample_name}' (e.g., 0-5, 7, 9-11)"
        ).strip()
        if not fovs_input:
            typer.secho(
                "A FOV specification is required.", err=True, fg=typer.colors.RED
            )
            continue
        try:
            parse_fov_range(fovs_input)
        except ValueError as exc:
            typer.secho(str(exc), err=True, fg=typer.colors.RED)
            continue
        return fovs_input


def _collect_samples_interactively() -> list[dict[str, str]]:
    """Collect sample definitions from the user."""
    samples: list[dict[str, str]] = []
    typer.echo("Configure your samples. Leave the name blank to finish.")
    while True:
        sample_name = typer.prompt("Sample name", default="").strip()
        if not sample_name:
            if samples:
                break
            typer.secho(
                "At least one sample is required.", err=True, fg=typer.colors.RED
            )
            continue
        if any(existing["name"] == sample_name for existing in samples):
            typer.secho(
                f"Sample '{sample_name}' already exists. Choose a different name.",
                err=True,
                fg=typer.colors.RED,
            )
            continue

        fovs_text = _prompt_fovs_for_sample(sample_name)
        samples.append({"name": sample_name, "fovs": fovs_text})
    return samples


def _prompt_path(prompt_text: str, default: Path | None = None) -> Path:
    """Prompt for a filesystem path."""
    while True:
        if default is not None:
            raw_value = typer.prompt(prompt_text, default=str(default)).strip()
        else:
            raw_value = typer.prompt(prompt_text).strip()
        if not raw_value:
            typer.secho("Please provide a path.", err=True, fg=typer.colors.RED)
            continue
        return Path(raw_value).expanduser()


def _prompt_existing_file(prompt_text: str, default: Path | None = None) -> Path:
    """Prompt for a file path that must exist."""
    while True:
        path = _prompt_path(prompt_text, default=default)
        if not path.exists():
            typer.secho(f"File '{path}' does not exist.", err=True, fg=typer.colors.RED)
            continue
        if not path.is_file():
            typer.secho(f"Path '{path}' is not a file.", err=True, fg=typer.colors.RED)
            continue
        return path


def _prompt_directory(
    prompt_text: str, default: Path | None = None, must_exist: bool = True
) -> Path:
    """Prompt for a directory path, optionally creating it."""
    while True:
        path = _prompt_path(prompt_text, default=default)
        if path.exists():
            if path.is_dir():
                return path
            typer.secho(
                f"Path '{path}' is not a directory.", err=True, fg=typer.colors.RED
            )
            continue
        if must_exist:
            typer.secho(
                f"Directory '{path}' does not exist.", err=True, fg=typer.colors.RED
            )
            continue
        path.mkdir(parents=True, exist_ok=True)
        return path


def _save_samples_yaml(path: Path, samples: list[dict[str, str]]) -> None:
    """Persist the samples list to YAML."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"samples": samples}, handle, sort_keys=False)


def workflow() -> None:
    """Run the chat-like wizard to assemble and execute a PyAMA workflow."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

    # Initialize feature options dynamically
    global PC_FEATURE_OPTIONS, FL_FEATURE_OPTIONS
    try:
        PC_FEATURE_OPTIONS = list_phase_features()
        FL_FEATURE_OPTIONS = list_fluorescence_features()

        if not PC_FEATURE_OPTIONS:
            typer.secho(
                "Warning: No phase contrast features found. Using default 'area' feature.",
                fg=typer.colors.YELLOW,
            )
            PC_FEATURE_OPTIONS = ["area"]

        if not FL_FEATURE_OPTIONS:
            typer.secho(
                "Warning: No fluorescence features found. Using default 'intensity_total' feature.",
                fg=typer.colors.YELLOW,
            )
            FL_FEATURE_OPTIONS = ["intensity_total"]

    except Exception as exc:
        typer.secho(
            f"Warning: Failed to discover features dynamically: {exc}. Using defaults.",
            fg=typer.colors.YELLOW,
        )
        PC_FEATURE_OPTIONS = ["area"]
        FL_FEATURE_OPTIONS = ["intensity_total"]

    typer.echo(
        "Welcome to pyama-air workflow! Let's collect the inputs for PyAMA processing.\n"
    )
    nd2_path = _prompt_nd2_path()

    typer.echo("\nLoading microscopy metadata...")
    try:
        image, metadata = load_microscopy_file(nd2_path)
        if hasattr(image, "close"):
            try:
                image.close()
            except Exception:  # pragma: no cover - best effort cleanup
                pass
    except Exception as exc:  # pragma: no cover - runtime path
        typer.secho(
            f"Failed to load microscopy file: {exc}", err=True, fg=typer.colors.RED
        )
        raise typer.Exit(code=1) from exc

    channel_names = metadata.channel_names or [
        f"C{i}" for i in range(metadata.n_channels)
    ]
    _print_channel_summary(channel_names)

    pc_channel = _prompt_channel(
        "Select the phase contrast (PC) channel index",
        range(len(channel_names)),
    )

    typer.echo(f"\nAvailable phase contrast features: {', '.join(PC_FEATURE_OPTIONS)}")
    pc_features = _prompt_features(f"PC channel [{pc_channel}]", PC_FEATURE_OPTIONS)
    typer.echo("")

    fl_feature_map: dict[int, set[str]] = defaultdict(set)

    typer.echo(
        "Configure fluorescence (FL) channels. Leave blank at any prompt to finish."
    )

    while True:
        entry = typer.prompt(
            "Select a fluorescence channel index (blank to finish)",
            default="",
        ).strip()
        if entry == "":
            break
        try:
            fl_channel = int(entry)
        except ValueError:
            typer.secho(
                "Please enter a numeric channel index.", err=True, fg=typer.colors.RED
            )
            continue
        if fl_channel == pc_channel:
            typer.secho(
                "Channel already used for PC. Pick a different channel.",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        if fl_channel not in range(len(channel_names)):
            typer.secho(
                f"Channel {fl_channel} is not valid. Available indices: {list(range(len(channel_names)))}",
                err=True,
                fg=typer.colors.RED,
            )
            continue

        typer.echo(f"Available fluorescence features: {', '.join(FL_FEATURE_OPTIONS)}")
        features = _prompt_features(f"FL channel [{fl_channel}]", FL_FEATURE_OPTIONS)
        if not features:
            typer.secho(
                "No features selected for this channel; skipping.",
                err=True,
                fg=typer.colors.YELLOW,
            )
            continue
        fl_feature_map[fl_channel].update(features)
        typer.echo("")

    output_dir_input = typer.prompt(
        "Enter output directory for results",
        default=str(nd2_path.parent),
    ).strip()
    output_dir = Path(output_dir_input).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Prompt for time units
    time_units_input = typer.prompt(
        "Time units for output (e.g., 'hours', 'minutes', 'seconds')", default="hours"
    ).strip()
    time_units = time_units_input if time_units_input else "hours"

    context = ProcessingContext(
        output_dir=output_dir,
        channels=Channels(
            pc=ChannelSelection(channel=pc_channel, features=sorted(pc_features)),
            fl=[
                ChannelSelection(channel=channel, features=sorted(features))
                for channel, features in sorted(fl_feature_map.items())
            ],
        ),
        params={},
        time_units=time_units,
    )

    typer.secho("\nPrepared context:", bold=True)
    typer.echo(context)

    default_fov_end = max(metadata.n_fovs - 1, 0)

    def _prompt_int(prompt_text: str, default: int, minimum: int = 0) -> int:
        while True:
            value = typer.prompt(prompt_text, default=str(default)).strip()
            try:
                number = int(value)
            except ValueError:
                typer.secho(
                    "Please enter an integer value.", err=True, fg=typer.colors.RED
                )
                continue
            if number < minimum:
                typer.secho(
                    f"Value must be >= {minimum}.",
                    err=True,
                    fg=typer.colors.RED,
                )
                continue
            return number

    fov_start = _prompt_int("FOV start", 0, minimum=0)
    fov_end = _prompt_int("FOV end", default_fov_end, minimum=fov_start)
    batch_size = _prompt_int("Batch size", 2, minimum=1)
    n_workers = _prompt_int("Number of workers", 1, minimum=1)

    typer.secho("\nStarting workflow...", bold=True)
    try:
        success = run_complete_workflow(
            metadata=metadata,
            context=context,
            fov_start=fov_start,
            fov_end=fov_end,
            batch_size=batch_size,
            n_workers=n_workers,
        )
    except Exception as exc:  # pragma: no cover - defensive
        typer.secho(f"Workflow failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    status = "SUCCESS" if success else "FAILED"
    color = typer.colors.GREEN if success else typer.colors.RED
    typer.secho(f"Workflow finished: {status}", bold=True, fg=color)


def merge() -> None:
    """Collect sample definitions and merge CSV outputs."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    typer.echo("Welcome to pyama-air merge! Let's gather the inputs for CSV merging.\n")

    samples = _collect_samples_interactively()
    typer.echo("")

    default_sample_yaml = Path.cwd() / "samples.yaml"
    sample_yaml_path = _prompt_path(
        "Enter the path to save samples.yaml",
        default=default_sample_yaml,
    )
    _save_samples_yaml(sample_yaml_path, samples)
    typer.secho(
        f"Saved {len(samples)} sample(s) to {sample_yaml_path}",
        fg=typer.colors.GREEN,
    )
    typer.echo("")

    default_processing = sample_yaml_path.parent / "processing_results.yaml"
    processing_results_path = _prompt_existing_file(
        "Enter the path to processing_results.yaml",
        default=default_processing if default_processing.exists() else None,
    )

    output_folder_default = sample_yaml_path.parent / "merge_output"
    output_folder = _prompt_directory(
        "Enter the output directory for merged CSV files",
        default=output_folder_default,
        must_exist=False,
    )

    typer.echo("")
    typer.secho("Starting merge...", bold=True)

    try:
        message = run_core_merge(
            sample_yaml=sample_yaml_path,
            processing_results=processing_results_path,
            output_dir=output_folder,
        )
    except Exception as exc:  # pragma: no cover - runtime path
        typer.secho(f"Merge failed: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    typer.secho(message, fg=typer.colors.GREEN, bold=True)


if __name__ == "__main__":  # pragma: no cover
    cli_app()

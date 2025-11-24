"""Command-line helpers for pyama-core."""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import typer
import yaml
from bioio import BioImage
from bioio_ome_tiff.writers import OmeTiffWriter
from tqdm.auto import tqdm

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

output_mode_option = typer.Option(
    "multi",
    "--mode",
    "-m",
    case_sensitive=False,
    help="Output mode: 'multi' (one OME-TIFF with all scenes) or 'split' (one OME-TIFF per scene).",
)


app = typer.Typer(help="pyama-core utilities")
logger = logging.getLogger(__name__)


def _collect_scenes(
    image: BioImage,
) -> tuple[list[object], list[str | None], list[str | None], list[list[str] | None]]:
    """Collect per-scene data, dimension orders, names, and channel names."""
    data_list: list[object] = []
    dim_orders: list[str | None] = []
    image_names: list[str | None] = []
    channel_names: list[list[str] | None] = []

    scenes = list(image.scenes)
    for idx, scene in enumerate(
        tqdm(scenes, desc="Reading scenes", unit="scene", leave=False)
    ):
        image.set_scene(scene)
        data_list.append(image.data)
        dim_orders.append(image.dims.order)
        # Some readers return string scene names; fallback to index label
        image_names.append(str(scene) if isinstance(scene, str) else f"Scene-{idx}")
        # Try to extract channel names from coordinates
        names: list[str] | None = None
        try:
            da = image.xarray_dask_data
            ch_coord = da.coords.get("C") if hasattr(da, "coords") else None
            if ch_coord is not None:
                try:
                    names = [str(v) for v in ch_coord.values.tolist()]
                except Exception:
                    names = [str(v) for v in list(ch_coord.values)]
        except Exception:
            names = None
        channel_names.append(names)

    return data_list, dim_orders, image_names, channel_names


@app.callback()
def main() -> None:
    """pyama-core utility commands."""
    # Configure basic logging so info-level messages are visible by default.
    if not logging.getLogger().handlers:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
        # Suppress verbose debug messages from fsspec (used by bioio)
        logging.getLogger("fsspec.local").setLevel(logging.WARNING)
    return None


@app.command()
def convert(
    input_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Input microscopy file (e.g., .nd2, .czi).",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "-o",
        "--output-dir",
        file_okay=False,
        dir_okay=True,
        writable=True,
        help="Directory to write the OME-TIFF. Defaults to the input file's directory.",
    ),
    mode: str = output_mode_option,
) -> None:
    """Convert a microscopy file (ND2, CZI, etc.) to a multi-scene OME-TIFF."""
    resolved_input = input_path.expanduser().resolve()
    target_dir = (
        output_dir.expanduser().resolve()
        if output_dir is not None
        else resolved_input.parent
    )
    resolved_output = target_dir / f"{resolved_input.stem}.ome.tiff"

    mode_normalized = mode.lower()
    if mode_normalized not in {"multi", "split"}:
        typer.echo("Invalid mode. Use 'multi' or 'split'.", err=True)
        raise typer.Exit(code=1)

    if mode_normalized == "multi":
        typer.echo(f"Converting {resolved_input} -> {resolved_output}")
        logger.info(
            "Converting microscopy file: %s -> %s", resolved_input, resolved_output
        )
    else:
        typer.echo(f"Converting {resolved_input} -> {target_dir} (one file per scene)")
        logger.info(
            "Converting microscopy file to split scenes: %s -> %s",
            resolved_input,
            target_dir,
        )
    try:
        image = BioImage(resolved_input)
    except Exception as exc:  # pragma: no cover - user-facing CLI path
        typer.echo(f"Failed to open microscopy file: {exc}", err=True)
        raise typer.Exit(code=1)

    target_dir.mkdir(parents=True, exist_ok=True)
    scene_data, dim_orders, image_names, channel_names = _collect_scenes(image)
    if not scene_data:
        typer.echo("No scenes found in the input file.", err=True)
        raise typer.Exit(code=1)

    typer.echo(f"Found {len(scene_data)} scene(s); writing OME-TIFF...")
    if mode_normalized == "multi":
        logger.info(
            "Saving OME-TIFF with %s scene(s) to %s", len(scene_data), resolved_output
        )
        try:
            OmeTiffWriter.save(
                scene_data,
                resolved_output,
                dim_order=dim_orders,
                image_name=image_names,
                channel_names=channel_names,
            )
        except Exception as exc:  # pragma: no cover - user-facing CLI path
            typer.echo(f"Failed to write OME-TIFF: {exc}", err=True)
            raise typer.Exit(code=1)

        logger.info("OME-TIFF saved to %s", resolved_output)
        typer.echo(f"Saved {len(scene_data)} scene(s) to {resolved_output}")
    else:
        saved_files: list[Path] = []
        for idx, (data, dim_order, name, ch_names) in enumerate(
            zip(scene_data, dim_orders, image_names, channel_names, strict=False)
        ):
            scene_output = target_dir / f"{resolved_input.stem}_scene{idx}.ome.tiff"
            logger.info("Saving scene %s to %s", name, scene_output)
            try:
                OmeTiffWriter.save(
                    data,
                    scene_output,
                    dim_order=dim_order,
                    image_name=name,
                    channel_names=ch_names,
                )
            except Exception as exc:  # pragma: no cover - user-facing CLI path
                typer.echo(f"Failed to write scene {idx}: {exc}", err=True)
                raise typer.Exit(code=1)
            saved_files.append(scene_output)

        logger.info("Saved %s scene files to %s", len(saved_files), target_dir)
        typer.echo(f"Saved {len(saved_files)} file(s) to {target_dir}")


# =============================================================================
# INTERACTIVE CLI COMMANDS
# =============================================================================

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


@app.command()
def workflow() -> None:
    """Run an interactive workflow wizard to process microscopy data."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)

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
        "Welcome to PyAMA workflow! Let's collect the inputs for PyAMA processing.\n"
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


@app.command()
def merge() -> None:
    """Run an interactive merge wizard to combine CSV outputs from multiple samples."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    # Suppress verbose debug messages from fsspec (used by bioio)
    logging.getLogger("fsspec.local").setLevel(logging.WARNING)
    typer.echo("Welcome to PyAMA merge! Let's gather the inputs for CSV merging.\n")

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


if __name__ == "__main__":
    app()

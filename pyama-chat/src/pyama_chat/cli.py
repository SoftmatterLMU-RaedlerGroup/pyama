"""Interactive CLI to build PyAMA processing contexts."""

from __future__ import annotations

import logging
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List

import typer

from pyama_core.io import load_microscopy_file
from pyama_core.processing.workflow.pipeline import run_complete_workflow
from pyama_core.processing.workflow.services.types import (
    ChannelSelection,
    Channels,
    ProcessingContext,
)

app = typer.Typer(
    add_completion=False,
    help="Guides you through selecting channels and features for PyAMA processing.",
)

PC_FEATURE_OPTIONS = ["area"]
FL_FEATURE_OPTIONS = ["intensity_total"]


def _prompt_nd2_path() -> Path:
    """Prompt until the user provides an ND2 path that exists."""
    while True:
        raw_path = typer.prompt("Enter the path to your ND2 file").strip()
        if not raw_path:
            typer.secho("Please provide a non-empty path.", err=True, fg=typer.colors.RED)
            continue
        nd2_path = Path(raw_path).expanduser()
        if not nd2_path.exists():
            typer.secho(f"Path '{nd2_path}' does not exist.", err=True, fg=typer.colors.RED)
            continue
        if not nd2_path.is_file():
            typer.secho(f"Path '{nd2_path}' is not a file.", err=True, fg=typer.colors.RED)
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
            typer.secho("Please enter a numeric channel index.", err=True, fg=typer.colors.RED)
            continue
        if selection not in valid_set:
            typer.secho(
                f"Channel {selection} is not in the available list: {sorted(valid_set)}",
                err=True,
                fg=typer.colors.RED,
            )
            continue
        return selection


def _prompt_features(channel_label: str, options: List[str]) -> List[str]:
    """Prompt for a set of features given a list of available options."""
    selected: list[str] = []
    for feature in options:
        if typer.confirm(f"Enable '{feature}' for {channel_label}?", default=True):
            selected.append(feature)
    return selected


def _print_channel_summary(channel_names: List[str]) -> None:
    typer.echo("")
    typer.secho("Discovered channels:", bold=True)
    for idx, name in enumerate(channel_names):
        label = name if name else f"C{idx}"
        typer.echo(f"  [{idx}] {label}")
    typer.echo("")


@app.command()
def build(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging output.",
    )
) -> None:
    """Run the chat-like wizard to assemble a PyAMA processing context."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    typer.echo("Welcome to pyama-chat! Let's collect the inputs for PyAMA processing.\n")
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
        typer.secho(f"Failed to load microscopy file: {exc}", err=True, fg=typer.colors.RED)
        raise typer.Exit(code=1) from exc

    channel_names = metadata.channel_names or [f"C{i}" for i in range(metadata.n_channels)]
    _print_channel_summary(channel_names)

    pc_channel = _prompt_channel(
        "Select the phase contrast (PC) channel index",
        range(len(channel_names)),
    )
    pc_features = _prompt_features(f"PC channel [{pc_channel}]", PC_FEATURE_OPTIONS)
    typer.echo("")

    fl_feature_map: Dict[int, set[str]] = defaultdict(set)

    typer.echo("Configure fluorescence (FL) channels. Leave blank at any prompt to finish.")

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
            typer.secho("Please enter a numeric channel index.", err=True, fg=typer.colors.RED)
            continue
        if fl_channel == pc_channel:
            typer.secho("Channel already used for PC. Pick a different channel.", err=True, fg=typer.colors.RED)
            continue
        if fl_channel not in range(len(channel_names)):
            typer.secho(
                f"Channel {fl_channel} is not valid. Available indices: {list(range(len(channel_names)))}",
                err=True,
                fg=typer.colors.RED,
            )
            continue

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
                typer.secho("Please enter an integer value.", err=True, fg=typer.colors.RED)
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


if __name__ == "__main__":  # pragma: no cover
    app()

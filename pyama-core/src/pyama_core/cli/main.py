"""Command-line helpers for pyama-core."""

import logging
from pathlib import Path

import typer
from bioio import BioImage
from bioio_ome_tiff.writers import OmeTiffWriter
from tqdm.auto import tqdm

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
    for idx, scene in enumerate(tqdm(scenes, desc="Reading scenes", unit="scene", leave=False)):
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
    return None


@app.command()
def convert(
    input_path: Path = typer.Argument(..., exists=True, file_okay=True, dir_okay=False, readable=True, help="Input microscopy file (e.g., .nd2, .czi)."),
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
    target_dir = output_dir.expanduser().resolve() if output_dir is not None else resolved_input.parent
    resolved_output = target_dir / f"{resolved_input.stem}.ome.tiff"

    mode_normalized = mode.lower()
    if mode_normalized not in {"multi", "split"}:
        typer.echo("Invalid mode. Use 'multi' or 'split'.", err=True)
        raise typer.Exit(code=1)

    if mode_normalized == "multi":
        typer.echo(f"Converting {resolved_input} -> {resolved_output}")
        logger.info("Converting microscopy file: %s -> %s", resolved_input, resolved_output)
    else:
        typer.echo(f"Converting {resolved_input} -> {target_dir} (one file per scene)")
        logger.info("Converting microscopy file to split scenes: %s -> %s", resolved_input, target_dir)
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
        logger.info("Saving OME-TIFF with %s scene(s) to %s", len(scene_data), resolved_output)
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


if __name__ == "__main__":
    app()

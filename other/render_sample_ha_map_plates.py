#!/usr/bin/env python3
"""Render the 36 directional zenith-angle HA layers for each shared city.

This display script is supplementary to the two mapping workflows. It reads
the precomputed, quantized HA layers distributed with the example data and
uses one fixed 0–90° colour scale for every city and azimuth.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import rasterio


PACKAGE = Path(__file__).resolve().parents[1]
SAMPLES = PACKAGE / "data" / "samples"
OUTPUT = PACKAGE / "figure"


def apply_figure_style(*, font: str = "Arial", sizes: tuple[int, int, int] = (8, 7, 6)) -> None:
    """Set a compact, portable publication style for the map plates."""
    base, secondary, tick = sizes
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [font, "Helvetica", "DejaVu Sans", "sans-serif"],
            "font.size": base,
            "axes.labelsize": base,
            "axes.titlesize": base,
            "legend.fontsize": secondary,
            "xtick.labelsize": tick,
            "ytick.labelsize": tick,
            "axes.linewidth": 0.6,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.spines.bottom": False,
            "legend.frameon": False,
            "figure.dpi": 200,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def load_metadata(city_dir: Path) -> dict:
    """Return the documented public metadata for one shared sample."""
    return json.loads((city_dir / "metadata.json").read_text(encoding="utf-8"))


def read_ha_band(src: rasterio.io.DatasetReader, band: int) -> np.ndarray:
    """Decode one HA band from its documented integer scale factor."""
    data = src.read(band, masked=True).astype(np.float32)
    scale_factor = float(src.tags().get("scale_factor", "1"))
    return data.filled(np.nan) * scale_factor


def assert_text_is_in_bounds(fig: mpl.figure.Figure) -> None:
    """Raise if any visible text falls outside the rendered figure."""
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    figure_box = fig.bbox
    overflow = []
    for text in fig.findobj(mpl.text.Text):
        if not text.get_visible() or not text.get_text().strip():
            continue
        box = text.get_window_extent(renderer)
        if (
            box.x0 < figure_box.x0
            or box.x1 > figure_box.x1
            or box.y0 < figure_box.y0
            or box.y1 > figure_box.y1
        ):
            overflow.append(text.get_text())
    if overflow:
        raise RuntimeError(f"Text falls outside the figure: {overflow}")


def render_city(city_dir: Path) -> None:
    """Write one 6 × 6 azimuth plate as high-resolution JPEG and PDF."""
    metadata = load_metadata(city_dir)
    city_name = metadata["city_name"]
    ha_path = city_dir / "ha_zenith_1000m_q0p01deg.tif"
    OUTPUT.mkdir(parents=True, exist_ok=True)

    apply_figure_style(font="Arial", sizes=(8, 7, 6))
    mpl.rcParams.update(
        {
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
            "image.interpolation": "nearest",
        }
    )
    fig, axes = plt.subplots(6, 6, figsize=(7.20, 7.55), dpi=600)
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.105, top=0.920, wspace=0.055, hspace=0.180)
    cmap = plt.get_cmap("cividis").copy()
    cmap.set_bad("white")
    image = None

    with rasterio.open(ha_path) as src:
        if src.count != 36:
            raise ValueError(f"Expected 36 HA layers in {ha_path.name}; found {src.count}.")
        for index, ax in enumerate(axes.flat, start=1):
            ha = read_ha_band(src, index)
            image = ax.imshow(ha, cmap=cmap, vmin=0.0, vmax=90.0, rasterized=True)
            azimuth = int(src.tags(index).get("azimuth_degrees", (index - 1) * 10))
            ax.set_title(f"{azimuth}°", fontsize=6, pad=1.5)
            ax.set_axis_off()

    if image is None:
        raise RuntimeError("No HA image layer was rendered.")
    fig.text(0.035, 0.965, city_name, ha="left", va="top", fontsize=9)
    fig.text(
        0.985,
        0.965,
        "Zenith-angle HA | 1 km × 1 km | azimuth clockwise from north",
        ha="right",
        va="top",
        fontsize=6,
    )
    colourbar_axis = fig.add_axes((0.26, 0.042, 0.48, 0.015))
    colourbar = fig.colorbar(image, cax=colourbar_axis, orientation="horizontal", ticks=[0, 30, 60, 90])
    colourbar.set_label("Zenith-angle HA (°)", fontsize=7, labelpad=2)
    colourbar.ax.tick_params(labelsize=6, direction="out", length=2, pad=1)
    assert_text_is_in_bounds(fig)

    stem = OUTPUT / f"{city_dir.name}_ha_0to350deg_10deg"
    fig.savefig(stem.with_suffix(".jpg"), dpi=600, pil_kwargs={"quality": 95, "subsampling": 0})
    fig.savefig(stem.with_suffix(".svg"))
    fig.savefig(stem.with_suffix(".pdf"), dpi=600)
    plt.close(fig)
    print(f"Wrote {stem.with_suffix('.jpg')}")
    print(f"Wrote {stem.with_suffix('.svg')}")
    print(f"Wrote {stem.with_suffix('.pdf')}")


def main() -> None:
    city_dirs = sorted(path for path in SAMPLES.iterdir() if path.is_dir())
    if not city_dirs:
        raise FileNotFoundError(f"No city samples found in {SAMPLES}")
    for city_dir in city_dirs:
        render_city(city_dir)


if __name__ == "__main__":
    main()

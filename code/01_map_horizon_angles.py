#!/usr/bin/env python3
"""Map 36 directional zenith-angle horizon layers from a 1 m DSM.

The script uses HORAYZON v1.2. Its native output is a horizon elevation angle
above horizontal; this script converts it to the zenith-angle HA used by the
shade condition solar_zenith > HA.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import horayzon as hray
import numpy as np
import rasterio
from affine import Affine
from scipy import ndimage


def nearest_fill(values: np.ndarray, invalid: np.ndarray) -> np.ndarray:
    """Fill DSM no-data cells with nearest valid elevations for mesh creation."""
    if not invalid.any():
        return values
    if invalid.all():
        raise ValueError("DSM contains no valid elevations.")
    indices = ndimage.distance_transform_edt(
        invalid, return_distances=False, return_indices=True
    )
    result = values.copy()
    result[invalid] = values[tuple(indices[:, invalid])]
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map 36 directional, zenith-angle HA layers from a 1 m DSM."
    )
    parser.add_argument(
        "--dsm", type=Path, required=True, help="Projected 1 m DSM in metres."
    )
    parser.add_argument(
        "--output", type=Path, required=True, help="36-band HA GeoTIFF."
    )
    parser.add_argument(
        "--output-size-m", type=int, default=1000, help="Central square output size."
    )
    parser.add_argument(
        "--buffer-m", type=int, default=500, help="DSM buffer retained on each side."
    )
    parser.add_argument(
        "--search-distance-m", type=float, default=500.0, help="Maximum ray length."
    )
    parser.add_argument(
        "--horizon-accuracy-deg",
        type=float,
        default=0.25,
        help="HORAYZON angular accuracy.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.output_size_m <= 0 or args.buffer_m <= 0 or args.search_distance_m <= 0:
        raise ValueError("Output size, buffer and search distance must be positive.")
    required_pixels = args.output_size_m + 2 * args.buffer_m

    with rasterio.open(args.dsm) as src:
        if src.count != 1:
            raise ValueError("DSM must contain one band.")
        if not np.isclose(src.res[0], 1.0) or not np.isclose(src.res[1], 1.0):
            raise ValueError("This example expects a 1 m DSM.")
        if not np.isclose(src.transform.b, 0.0) or not np.isclose(src.transform.d, 0.0):
            raise ValueError("DSM must be north-up without grid rotation.")
        dsm = src.read(1).astype(np.float32)
        profile = src.profile.copy()
        invalid = ~np.isfinite(dsm)
        if src.nodata is not None:
            invalid |= dsm == src.nodata
        dsm = nearest_fill(dsm, invalid)

        if src.height < required_pixels or src.width < required_pixels:
            raise ValueError(
                f"DSM must be at least {required_pixels} x {required_pixels} pixels "
                "for the selected output and buffer."
            )
        row0 = (src.height - required_pixels) // 2
        col0 = (src.width - required_pixels) // 2
        dsm = dsm[row0 : row0 + required_pixels, col0 : col0 + required_pixels]
        transform = src.transform * Affine.translation(col0, row0)

    x = transform.c + (np.arange(required_pixels, dtype=np.float32) + 0.5) * transform.a
    y = transform.f + (np.arange(required_pixels, dtype=np.float32) + 0.5) * transform.e
    x_grid, y_grid = np.meshgrid(x, y)
    vertices = hray.auxiliary.rearrange_pad_buffer(x_grid, y_grid, dsm)

    output_shape = (args.output_size_m, args.output_size_m)
    vec_norm = np.zeros((*output_shape, 3), dtype=np.float32)
    vec_norm[:, :, 2] = 1.0
    vec_north = np.zeros((*output_shape, 3), dtype=np.float32)
    vec_north[:, :, 1] = 1.0

    horizon_rad, azimuth_rad = hray.horizon.horizon_gridded(
        vertices,
        required_pixels,
        required_pixels,
        vec_norm,
        vec_north,
        args.buffer_m,
        args.buffer_m,
        dist_search=args.search_distance_m / 1000.0,
        azim_num=36,
        hori_acc=args.horizon_accuracy_deg,
        ray_algorithm="binary_search",
        geom_type="grid",
        elev_ang_low_lim=-89.0,
        ray_org_elev=0.01,
    )
    azimuth_degrees = np.degrees(azimuth_rad) % 360.0
    expected = np.arange(0, 360, 10, dtype=float)
    if not np.allclose(azimuth_degrees, expected, atol=1e-5):
        raise RuntimeError(f"Unexpected azimuth sequence: {azimuth_degrees}")

    elevation_deg = np.maximum(np.degrees(np.moveaxis(horizon_rad, 2, 0)), 0.0)
    ha_zenith_deg = (90.0 - elevation_deg).astype(np.float32)
    output_transform = transform * Affine.translation(args.buffer_m, args.buffer_m)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.update(
        driver="GTiff",
        height=args.output_size_m,
        width=args.output_size_m,
        count=36,
        dtype="float32",
        nodata=-9999.0,
        transform=output_transform,
        compress="deflate",
        predictor=3,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(args.output, "w", **profile) as dst:
        dst.write(ha_zenith_deg)
        dst.update_tags(
            angle_definition="zenith-angle threshold in degrees",
            shade_rule="cast shade where solar zenith angle > HA",
            azimuth_reference="clockwise from north",
            azimuth_step_degrees=10,
            source_dsm_units="metres",
            output_size_m=args.output_size_m,
            input_buffer_m=args.buffer_m,
            horizon_search_distance_m=args.search_distance_m,
            horizon_accuracy_degrees=args.horizon_accuracy_deg,
            algorithm="HORAYZON v1.2 horizon_gridded; binary_search",
        )
        for band, azimuth in enumerate(expected.astype(int), start=1):
            dst.set_band_description(band, f"HA_zenith_{azimuth:03d}deg")
            dst.update_tags(band, azimuth_degrees=int(azimuth))

    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "output": str(args.output),
        "angle_definition": "zenith-angle threshold; HA = 90 - horizon elevation",
        "output_shape_pixels": [args.output_size_m, args.output_size_m],
        "buffer_m": args.buffer_m,
        "search_distance_m": args.search_distance_m,
        "azimuths_degrees": expected.astype(int).tolist(),
        "ha_zenith_min_deg": float(np.nanmin(ha_zenith_deg)),
        "ha_zenith_mean_deg": float(np.nanmean(ha_zenith_deg)),
        "ha_zenith_max_deg": float(np.nanmax(ha_zenith_deg)),
    }
    summary_path = args.output.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()

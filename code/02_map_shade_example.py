#!/usr/bin/env python3
"""Map single-time cast shade, tree self-shade and total shade.

Example default: 15 July 2020, 14:00 local civil time. The HA input must be
the 36-band zenith-angle output from 01_map_horizon_angles.py.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pvlib
import rasterio
from rasterio.warp import Resampling, reproject


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Map cast shade and tree self-shade for one local time."
    )
    parser.add_argument("--ha", type=Path, required=True, help="36-band zenith-angle HA GeoTIFF.")
    parser.add_argument(
        "--hag",
        type=Path,
        required=True,
        help="LiDAR-derived 1 m HAG raster co-registered with the HA grid.",
    )
    parser.add_argument("--resulc", type=Path, required=True, help="Categorical land-cover raster.")
    parser.add_argument(
        "--metadata",
        type=Path,
        required=True,
        help="JSON with latitude, longitude and timezone.",
    )
    parser.add_argument("--output", type=Path, required=True, help="Four-band shade GeoTIFF.")
    parser.add_argument(
        "--local-time",
        default="2020-07-15 14:00",
        help="Local civil time formatted as YYYY-MM-DD HH:MM.",
    )
    parser.add_argument("--tree-class", type=int, default=2, help="Tree-cover class in resULC.")
    parser.add_argument("--minimum-tree-height-m", type=float, default=2.0)
    parser.add_argument("--maximum-tree-height-m", type=float, default=60.0)
    parser.add_argument("--hag-nodata", type=float, default=-9999.0)
    return parser.parse_args()


def resample_to_ha_grid(
    path: Path,
    reference: rasterio.io.DatasetReader,
    resampling: Resampling,
    source_nodata: float | None,
    dtype: str,
) -> np.ndarray:
    """Reproject one raster to the HA grid and preserve its measurement type."""
    destination = np.full((reference.height, reference.width), np.nan, dtype=dtype)
    with rasterio.open(path) as src:
        reproject(
            source=rasterio.band(src, 1),
            destination=destination,
            src_transform=src.transform,
            src_crs=src.crs,
            src_nodata=source_nodata if source_nodata is not None else src.nodata,
            dst_transform=reference.transform,
            dst_crs=reference.crs,
            dst_nodata=np.nan,
            resampling=resampling,
        )
    return destination


def read_aligned_hag(
    path: Path,
    reference: rasterio.io.DatasetReader,
    source_nodata: float | None,
) -> np.ndarray:
    """Read a native 1 m HAG raster after strict co-registration checks."""
    with rasterio.open(path) as src:
        same_grid = (
            src.count == 1
            and src.width == reference.width
            and src.height == reference.height
            and src.crs == reference.crs
            and src.transform.almost_equals(reference.transform)
        )
        if not same_grid:
            raise ValueError(
                "HAG must be a single-band, native 1 m raster co-registered "
                "with the HA grid; HAG resampling is intentionally disabled."
            )
        hag = src.read(1).astype(np.float32)
        nodata = source_nodata if source_nodata is not None else src.nodata
        if nodata is not None:
            hag[hag == nodata] = np.nan
    return hag


def main() -> None:
    args = parse_args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    local_time = pd.Timestamp(args.local_time).tz_localize(metadata["timezone"])
    solar = pvlib.solarposition.get_solarposition(
        time=local_time,
        latitude=float(metadata["latitude"]),
        longitude=float(metadata["longitude"]),
    ).iloc[0]
    solar_zenith = float(solar["apparent_zenith"])
    solar_azimuth = float(solar["azimuth"]) % 360.0
    if solar_zenith >= 90.0:
        raise ValueError("The requested time is not daytime at the supplied city location.")
    band_index = int(np.floor((solar_azimuth + 5.0) % 360.0 / 10.0))

    with rasterio.open(args.ha) as ha_ds:
        if ha_ds.count != 36:
            raise ValueError("HA input must contain 36 bands at 10 degree azimuth intervals.")
        ha = ha_ds.read(band_index + 1).astype(np.float32)
        if ha_ds.nodata is not None:
            ha[ha == ha_ds.nodata] = np.nan
        ha_scale_factor = float(ha_ds.tags().get("scale_factor", 1.0))
        ha *= ha_scale_factor
        hag = read_aligned_hag(args.hag, ha_ds, args.hag_nodata)
        resulc = resample_to_ha_grid(
            args.resulc, ha_ds, Resampling.nearest, None, "float32"
        )
        profile = ha_ds.profile.copy()

    valid_ha = np.isfinite(ha) & (ha >= 0.0) & (ha <= 90.0)
    cast_shade = valid_ha & (solar_zenith > ha)
    tree_mask = (
        np.isfinite(hag)
        & (resulc == args.tree_class)
        & (hag > args.minimum_tree_height_m)
        & (hag < args.maximum_tree_height_m)
    )
    total_shade = cast_shade | tree_mask

    output = np.full((4, profile["height"], profile["width"]), 255, dtype=np.uint8)
    output[0, valid_ha] = cast_shade[valid_ha].astype(np.uint8)
    output[1, valid_ha] = tree_mask[valid_ha].astype(np.uint8)
    output[2, valid_ha] = total_shade[valid_ha].astype(np.uint8)
    output[3, valid_ha] = 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    profile.update(
        driver="GTiff",
        count=4,
        dtype="uint8",
        nodata=255,
        compress="deflate",
        predictor=2,
        tiled=True,
        blockxsize=256,
        blockysize=256,
    )
    with rasterio.open(args.output, "w", **profile) as dst:
        dst.write(output)
        dst.set_band_description(1, "casting_shade")
        dst.set_band_description(2, "tree_self_shade")
        dst.set_band_description(3, "total_shade")
        dst.set_band_description(4, "valid_HA")
        dst.update_tags(
            local_time=str(local_time),
            solar_zenith_degrees=solar_zenith,
            solar_azimuth_degrees=solar_azimuth,
            selected_ha_azimuth_degrees=band_index * 10,
            ha_scale_factor=ha_scale_factor,
            casting_rule="solar zenith > selected zenith-angle HA",
            tree_rule=(
                f"resULC == {args.tree_class} AND "
                f"{args.minimum_tree_height_m} < HAG < {args.maximum_tree_height_m} m"
            ),
            total_shade_rule="casting shade OR tree self-shade",
            hag_grid="native 1 m LiDAR-derived HAG co-registered with HA; no resampling",
            resulc_resampling="nearest neighbour to 1 m HA grid",
        )

    valid_count = int(valid_ha.sum())
    summary = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "local_time": str(local_time),
        "solar_zenith_degrees": solar_zenith,
        "solar_azimuth_degrees": solar_azimuth,
        "selected_ha_azimuth_degrees": band_index * 10,
        "valid_HA_pixels": valid_count,
        "casting_shade_fraction": float(cast_shade[valid_ha].mean()) if valid_count else None,
        "tree_self_shade_fraction": float(tree_mask[valid_ha].mean()) if valid_count else None,
        "total_shade_fraction": float(total_shade[valid_ha].mean()) if valid_count else None,
    }
    summary_path = args.output.with_suffix(".json")
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"Wrote {args.output}")
    print(f"Wrote {summary_path}")


if __name__ == "__main__":
    main()

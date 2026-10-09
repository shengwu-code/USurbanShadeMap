# Example input data

The repository supplies compact 1 m examples for three US urban areas:

| Directory | City | DSM support domain | HA/shade output domain |
|---|---|---:|---:|
| los_angeles_ca | Los Angeles, CA | 2 km x 2 km | central 1 km x 1 km |
| st_louis_mo | St. Louis, MO | 2 km x 2 km | central 1 km x 1 km |
| duluth_mn | Duluth, MN | 2 km x 2 km | central 1 km x 1 km |

Each city directory contains:

- dsm_2000m_1m_m.tif: 1 m LiDAR-derived DSM in metres. It includes the 500 m
  buffer used for HA ray tracing.
- hag_1000m_1m_m.tif: native 1 m height above ground in metres, derived from
  the normalized LiDAR point cloud and co-registered with the central 1 m HA
  grid. Script 2 reads these values directly and performs no HAG resampling.
- resulc_1000m.tif: NAIP-based categorical land cover. Class 2 is tree cover;
  Script 2 uses nearest-neighbour resampling.
- ha_zenith_1000m_q0p01deg.tif: precomputed 36-band zenith-angle HA result.
  Pixel values are stored as UInt16 and multiplied by the GeoTIFF scale_factor
  tag of 0.01 degree. The 0.01 degree storage precision is much finer than the
  0.25 degree HORAYZON horizon accuracy used here.
- metadata.json: city coordinates, time zone and sample-grid information.

Data provenance:

- DSM and HAG: USGS 3DEP LiDAR-derived city products processed for this study.
- resULC: mosaicked NAIP-based urban land-cover products from the regional
  Earth Engine assets documented in the manuscript.

The examples are for code demonstration and should not be interpreted as a
stand-alone national data release. The full 3DEP, HAG and land-cover sources
are subject to their respective data-provider terms.

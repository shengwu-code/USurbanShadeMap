# High-resolution urban shade mapping

Minimal, reproducible code accompanying a study on high-resolution urban shade
mapping. The repository contains two scripts:

1. code/01_map_horizon_angles.py computes 36 directional horizon-angle (HA)
   layers from a 1 m digital surface model (DSM) using HORAYZON v1.2.
2. code/02_map_shade_example.py combines those HA layers with height above
   ground (HAG) and NAIP-based urban land cover (resULC) to map cast shade,
   tree self-shade and their union for 15 July 2020 at 14:00 local time.

The three included examples are Los Angeles, CA; St. Louis, MO; and Duluth,
MN. They are small, real-data subsets intended to demonstrate the workflow,
not to reproduce citywide study products.

## Scientific definitions

HORAYZON returns a horizon **elevation** angle, alpha, measured upward from
the horizontal plane. The study HA is a **zenith-angle threshold**,
theta_HA = 90 degrees - max(alpha, 0), because a pixel is in cast shade when
solar zenith angle Z exceeds the directional threshold:

cast shade = (Z > theta_HA)

Tree self-shade is defined where resULC equals 2 and 2 < HAG < 60 m. Total
shade is the union of cast shade and tree self-shade. This small example
intentionally excludes atmospheric cloud effects and partial canopy
transmission used in selected study analyses.

## Repository layout

    code/                 Two executable workflow scripts
    data/samples/         Three compact, real-data example subsets
    data/README.md        Input definitions and provenance
    other/                Optional display and verification utilities
    figure/               HA map plates generated from the shared examples
    manuscript/           Code-availability text template
    environment.yml       Reproducible Conda environment
    THIRD_PARTY_NOTICES.md

Each sample contains a 2 km x 2 km, 1 m DSM in metres. The scripts produce HA
for its central 1 km x 1 km region, retaining a 500 m margin for a 500 m
horizon search. HAG and resULC samples cover that central output grid.

## Installation

HORAYZON is compiled against Intel Embree and TBB. The official HORAYZON
installation is recommended on Linux, macOS or Windows Subsystem for Linux
(WSL); native Windows support is not assumed here.

    conda env create -f environment.yml
    conda activate urban-shade-ha
    git clone https://github.com/ChristianSteger/HORAYZON.git third_party/HORAYZON
    python -m pip install ./third_party/HORAYZON

The commands follow the HORAYZON v1.2 installation approach. If compilation
fails, consult the official HORAYZON documentation for Embree/TBB platform
requirements.

## Quick start

Run each command from the repository root. The first script creates a
36-band GeoTIFF whose bands represent azimuths 0, 10, ..., 350 degrees,
clockwise from north.

    python code/01_map_horizon_angles.py \
      --dsm data/samples/los_angeles_ca/dsm_2000m_1m_m.tif \
      --output results/los_angeles_ca_ha_zenith_1000m.tif

    python code/02_map_shade_example.py \
      --ha results/los_angeles_ca_ha_zenith_1000m.tif \
      --hag data/samples/los_angeles_ca/hag_1000m_source.tif \
      --resulc data/samples/los_angeles_ca/resulc_1000m.tif \
      --metadata data/samples/los_angeles_ca/metadata.json \
      --output results/los_angeles_ca_shade_20200715_1400.tif

Repeat the two commands after replacing los_angeles_ca with st_louis_mo or
duluth_mn.

Precomputed 36-band HA files are also supplied in each sample directory. They
are stored as UInt16 with a scale factor of 0.01 degree to keep the repository
compact; Script 2 reads this scale factor automatically. Use the precomputed
file as the HA input to run the shade example without first executing Script 1.

## Optional spatial display of HA

To inspect the directional HA distribution, the following display-only helper
renders a 6 x 6 map plate for each sample city. Each cell is one azimuth from
0° to 350° at 10° intervals. All maps use the same 0–90° zenith-angle HA
colour scale, so spatial patterns can be compared directly across the three
cities.

    python other/render_sample_ha_map_plates.py

It writes high-resolution JPEG, editable SVG and PDF files in `figure/`.

## Input requirements for new locations

- DSM: projected, north-up raster at 1 m resolution, in **metres**. The DSM
  must include at least the output domain plus the chosen buffer on all sides.
- HAG: a metric raster. It may have another resolution or alignment: Script 2
  resamples it bilinearly to the 1 m HA grid.
- resULC: a categorical land-cover raster. It is resampled with nearest
  neighbour; tree cover must use class code 2, or pass another value through
  the --tree-class option.
- Metadata JSON: latitude, longitude and IANA timezone.

The example's 500 m buffer and 500 m search distance should be increased
together if longer shadows are relevant. The output edge should never be used
unless the DSM has a matching support buffer.

## Reproducibility notes

- The solar location is represented by the sample city centroid, consistent
  with the study workflow.
- Solar azimuth is clockwise from north and is assigned to the nearest 10
  degree HA band.
- The example uses local civil time, so each city's IANA time zone is stored
  in its metadata.
- The scripts write GeoTIFF metadata and a JSON summary beside each output.

Before public release, add a repository license selected by the copyright
holders, complete the code-availability URL template, and archive the tagged
release in a persistent repository such as Zenodo.

# Example verification

Both scripts were run sequentially for all three bundled 2 km DSM samples
using the default local time of 15 July 2020, 14:00. The following output
values provide a compact check that a local installation is behaving as
expected. Values can vary slightly with library versions and solar-position
settings.

| City | Selected HA azimuth | Solar zenith | Cast shade | Tree self-shade | Total shade |
|---|---:|---:|---:|---:|---:|
| Los Angeles, CA | 230 degrees | 18.53 degrees | 0.01 | 0.10 | 0.11 |
| St. Louis, MO | 220 degrees | 20.64 degrees | 0.03 | 0.33 | 0.34 |
| Duluth, MN | 200 degrees | 27.03 degrees | 0.03 | 0.20 | 0.22 |

Fractions are calculated over all valid cells in each central 1 km x 1 km
output. The HORAYZON core ray-tracing stage completed in approximately
3.7-3.9 seconds per sample on the validation workstation; total command time
also includes environment startup and raster input/output.

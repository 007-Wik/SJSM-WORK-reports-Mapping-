# Instructions — Tuljapur + Lohara Map Data

Script: `tuljapur_lohara_map_data.py`. Output: `map_data/<theme>/`. All rasters EPSG:32643 (UTM 43N). All data clipped to your GeoJSON blocks.

## 1. Install

```bash
pip install earthengine-api geemap geopandas rasterio shapely osmnx contourpy whitebox scipy
earthengine authenticate
```

- Need a GEE-enabled Google Cloud project ID.

## 2. Check GeoJSON

```bash
python -c "import geopandas as g; d=g.read_file(r'blocks.geojson'); print(d.crs); print(d.columns.tolist()); print(d.head())"
```

- Find the column holding block names.
- Edit CONFIG at top of script:

```python
GEE_PROJECT    = "your-gcp-project-id"
AOI_VECTOR     = r"C:/path/blocks.geojson"
AOI_NAME_FIELD = "<column from above>"
AOI_NAMES      = ["Tuljapur", "Lohara"]   # [] = use all features in file
```

- Names match case-insensitive. No match → script exits and prints available values.
- Spelling in file may differ (e.g. `Tuljapur` / `Tuljapur Tehsil`). Fix `AOI_NAMES` to match exactly.
- First output to verify: `map_data/aoi/aoi_blocks.gpkg`. Open in QGIS. Confirm only the two blocks.

## 3. Run

```bash
python tuljapur_lohara_map_data.py --project YOUR_GCP_PROJECT --themes all
python tuljapur_lohara_map_data.py --themes hillshade dem slope     # subset
python tuljapur_lohara_map_data.py --themes lulc --mode drive       # export to Drive
```

Themes: `roads lulc dem hillshade slope streams soil_depth lithology geology rainfall ndvi`.

- Order matters for `streams`: needs `dem_buffered.tif`. Auto-runs `dem` if missing (local mode only).
- Each theme fails independently. Check log for `FAILED`.
- Large 10 m downloads (LULC, NDVI) slow. Use `--mode drive` if local timeout.

## 4. Outputs

| Theme | Files |
|---|---|
| aoi | `aoi_blocks.gpkg` |
| roads | `roads_osm.gpkg` (`road_class`) |
| lulc | `lulc_<esri\|worldcover>_<year>.tif`, `*_area_table.csv` |
| dem | `dem_aoi.tif`, `dem_buffered.tif`, `contours_10m.gpkg` (`elev`, `index`) |
| hillshade | `hillshade_z2.tif` (unclipped, AOI + 2 km frame) |
| slope | `slope_deg_pct.tif` (band 1 deg, band 2 %) |
| streams | `streams_strahler.gpkg`, `drainage_density_grid.gpkg`, `stream_order_summary.csv` |
| soil_depth | `BDRICM_cm_250m.tif`, `BDTICM_cm_250m.tif` |
| lithology / geology | `lithology.gpkg`, `geology.gpkg` |
| rainfall | `rain_mean_mm_*.tif` (annual + 4 seasons), `rain_cv_pct.tif`, `rain_annual_trend_mm_per_yr.tif`, `rain_timeseries_aoi_mean_mm.csv` |
| ndvi | annual mean, kharif median, rabi median tifs |
| root | `legend_specs.json`, `manifest.json` |

## 5. Hillshade — basemap for ALL maps

- Source: Copernicus GLO-30 (30 m). Az 315°, alt 45°, vertical exaggeration Z=2 (flat Deccan terrain). Tune in CONFIG: `HILLSHADE_AZIMUTH`, `HILLSHADE_ALTITUDE`, `HILLSHADE_Z`.
- Same file on every map → consistent look.
- QGIS layer stack, bottom → top:
  1. `hillshade_z2.tif` — greyscale, 0–255
  2. Thematic raster/vector — **blend mode Multiply**, or opacity 60–75 %
  3. Block boundary (`aoi_blocks.gpkg`) — no fill, 1.2 pt dark line
  4. Labels
- Exceptions: DEM map → hypsometric tint over hillshade, opacity ~55 %. Slope map → thin hillshade opacity or none (slope already shows relief).
- Clip hillshade to block boundary in layout (clip mask), or keep 2 km frame for context.

## 6. LULC — priority

1. **Esri 10 m Annual LULC**, year `LULC_YEAR` (2025). Accepts up to `LULC_MAX_YEAR_GAP` (1) years older.
2. Else **ESA WorldCover v200 (2021)**, auto-fallback.

- Check log + `manifest.json` → `product`, `year_used`. **Update map subtitle to match.** Warning `!!!` in log = fallback happened.
- Class codes differ between products. Legend from `legend_specs.json` (`lulc_esri` or `lulc_worldcover`). Area table CSV has `hex` column for same colours.
- Esri 2025 availability in sat-io asset unverified.

## 7. Data you must supply / verify

- **Lithology + geology**: not in GEE at useful scale. Download from GSI Bhukosh (bhukosh.gsi.gov.in), set in CONFIG:
  ```python
  LITHOLOGY_SRC = r"C:/path/lithology.shp"   # or "ee:<asset id>"
  GEOLOGY_SRC   = r"C:/path/geology.shp"
  ```
  Re-run `--themes lithology geology`. Log lists attribute columns → pick symbology field.
- **Soil depth**: ISRIC 2017 BDRICM (cap 200 cm) and BDTICM (absolute). 250 m → blocky. If HTTP read fails, log prints URL; download, clip manually.
- **Rainfall**: CHIRPS 5.5 km → ~10×10 px over AOI. Present as coarse. Period `RAIN_START`–`RAIN_END` (1991–2025).
- **Streams**: derived from 30 m DEM, threshold `STREAM_THRESHOLD_KM2 = 1.0`. Raise to 2–5 if network too dense; lower if too sparse. Uses 10 km buffered DEM so flow accumulation valid at boundary.
- **Roads**: OSM completeness varies in rural Maharashtra. State in source line.
- **NDVI**: kharif composite may stay cloud-affected. Check coverage.

## 8. Layout standard (all 10 maps)

- Separate map per theme. Same page size, margins, fonts, scale.
- Title = theme. Subtitle = dataset + year/period + "Tuljapur and Lohara Blocks".
- North arrow, scale bar, UTM 43N graticule, block names.
- Legend: title, units, classes from `legend_specs.json`. Same position every map.
- Source line from `manifest.json` (bottom).
- Colours: sequential ramps for continuous (slope, NDVI, rainfall, soil depth), categorical for LULC/lithology/geology, same class = same colour on every map.
- Slope classes (%): 0–1, 1–3, 3–5, 5–10, 10–15, 15–35, >35. Soil depth classes (cm): <10, 10–25, 25–50, 50–100, 100–150, >150. NBSS-style defaults — verify against project standard.
- DEM map: contours 10 m thin grey, index every 50 m thicker + labelled.

## 9. Troubleshooting

| Error | Fix |
|---|---|
| `AOI missing` | Check `AOI_VECTOR` path exists |
| `No match for [...]` | Fix `AOI_NAME_FIELD` / `AOI_NAMES` |
| EE auth / project error | `earthengine authenticate`; confirm project has Earth Engine API enabled |
| `User memory limit exceeded` / `Computation timed out` | Use `--mode drive` |
| `pip install whitebox` | Streams skipped until installed |
| Stream shapefile column error | Open `streams/streams_raw.shp`, check attribute name; script looks for `STRM_VAL`/`VALUE`/`STRAHLER`, else first numeric column |

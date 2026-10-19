#!/usr/bin/env python3
"""
Tuljapur + Lohara blocks (Dharashiv / Osmanabad, Maharashtra)
Thematic map data downloader & processor -- GEE + local processing where GEE has no dataset.

THEMES
  roads       OSM highways via osmnx                                  -> gpkg
  lulc        Esri 10 m Annual LULC (sat-io TS collection)           -> tif + area table + legend
  dem         Copernicus GLO-30 (or SRTM) + 10 m contours (local)    -> tif + gpkg
  slope       from DEM (degrees + percent)                           -> tif
  streams     Strahler order + drainage density (WhiteboxTools, 3km2) -> gpkg + geojson
  soil_depth  ISRIC SoilGrids / National NBSS&LUP soil depth         -> tif + area summary
  lithology   CGWB Litholog observation wells clipped to AOI         -> gpkg + geojson
  rainfall    CHIRPS: mean annual + 4 IMD seasons, CV, trend, CSV    -> tif + csv
  ndvi        Sentinel-2 SR + Cloud Score+ : annual mean, kharif, rabi -> tif
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from datetime import datetime
from pathlib import Path

import ee
import geemap
import geopandas as gpd
import numpy as np
import rasterio
from rasterio.merge import merge
from shapely.geometry import box, mapping

# =====================================================================
# CONFIG & PATHS
# =====================================================================
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(Path(__file__).resolve().parent))
OUT_DIR = BASE_DIR / "map_data"
GEE_PROJECT = "lulc-473418"
EXPORT_MODE = "local"                 # "local" (direct download) | "drive" (Export.image.toDrive)
DRIVE_FOLDER = "Tuljapur_Lohara_maps"
UTM_CRS = "EPSG:32643"                # UTM 43N metric projection

# --- AOI: block boundaries ---
AOI_VECTOR = OUT_DIR / "aoi" / "aoi_blocks.gpkg"
AOI_ASSET = ""
AOI_NAME_FIELD = "NAME"
AOI_NAMES = ["Tuljapur", "Lohara"]
ALLOW_DISTRICT_FALLBACK = False

# --- DEM / terrain ---
DEM_SOURCE = "COPERNICUS"             # "COPERNICUS" (GLO-30) | "SRTM" (30 m)
DEM_SCALE = 30
DEM_BUFFER_M = 4000                   # 4 km buffer for hydrology flow routing (fast & robust)
CONTOUR_INTERVAL = 10                 # m
CONTOUR_INDEX_EVERY = 50              # m
CONTOUR_SMOOTH_SIGMA = 1.0            # Gaussian smoothing sigma
STREAM_THRESHOLD_KM2 = 3.0            # 3.0 km2 threshold for major/highest streams
DD_CELL_M = 1000                      # 1 km drainage density grid

# --- LULC ---
LULC_YEAR = 2024                      # Latest available year
ESRI_LULC_ASSET = "projects/sat-io/open-datasets/landcover/ESRI_Global-LULC_10m_TS"
LULC_SCALE = 10

# --- Soil depth ---
ISRIC_URLS = {
    "BDRICM": "https://files.isric.org/soilgrids/former/2017-03-10/data/BDRICM_M_250m_ll.tif",
    "BDTICM": "https://files.isric.org/soilgrids/former/2017-03-10/data/BDTICM_M_250m_ll.tif",
}
SOIL_DEPTH_GEE_ASSET = ""

# --- Lithology ---
LITHOLOGY_SRC = str(BASE_DIR / "data" / "Litholog.geojson")
GEOLOGY_SRC = ""

# --- Rainfall ---
RAIN_START, RAIN_END = 1991, 2024
RAIN_SCALE = 5566                     # CHIRPS native 0.05 deg (~5.5 km)
SEASONS = {
    "winter": (1, 3),
    "premonsoon": (3, 6),
    "monsoon": (6, 10),
    "postmonsoon": (10, 13),
}

# --- NDVI ---
NDVI_YEAR = 2024
NDVI_SCALE = 10
CS_THRESHOLD = 0.6                    # Cloud Score+ cs_cdf threshold
NDVI_PERIODS = {
    "annual_mean": (f"{NDVI_YEAR}-01-01", f"{NDVI_YEAR + 1}-01-01", "mean"),
    "kharif_median": (f"{NDVI_YEAR}-06-01", f"{NDVI_YEAR}-11-01", "median"),
    "rabi_median": (f"{NDVI_YEAR}-11-01", f"{NDVI_YEAR + 1}-03-01", "median"),
}

# --- Legends ---
LEGENDS = {
    "lulc_esri": {
        1: ("Water", "#1A5BAB"), 2: ("Trees", "#358221"), 4: ("Flooded vegetation", "#87D19E"),
        5: ("Crops", "#FFDB5C"), 7: ("Built area", "#ED022A"), 8: ("Bare ground", "#EDE9E4"),
        9: ("Snow/ice", "#F2FAFF"), 10: ("Clouds", "#C8C8C8"), 11: ("Rangeland", "#C6AD8D"),
    },
    "slope_pct_nbss": {
        "breaks": [0, 1, 3, 5, 10, 15, 35, 1000],
        "labels": ["0-1 Nearly level", "1-3 Very gently sloping", "3-5 Gently sloping",
                   "5-10 Moderately sloping", "10-15 Strongly sloping",
                   "15-35 Moderately steep", ">35 Steep"],
    },
    "soil_depth_cm_nbss": {
        "breaks": [0, 10, 25, 50, 100, 150, 100000],
        "labels": ["<10 Very shallow", "10-25 Shallow", "25-50 Moderately shallow",
                   "50-100 Moderately deep", "100-150 Deep", ">150 Very deep"],
    },
    "ndvi": {
        "breaks": [-1, 0, 0.15, 0.3, 0.45, 0.6, 1],
        "labels": ["<0 Water/non-veg", "0-0.15 Bare/built", "0.15-0.3 Sparse",
                   "0.3-0.45 Moderate", "0.45-0.6 Dense", ">0.6 Very dense"],
    },
}

SOURCES = {
    "roads": "OpenStreetMap contributors (ODbL)",
    "lulc": "Esri/Impact Observatory 10 m Annual Land Use Land Cover",
    "dem": "Copernicus GLO-30 30m DEM",
    "slope": "Derived from Copernicus DEM (UTM 43N)",
    "streams": "Derived from DEM using WhiteboxTools (D8, 3km² threshold)",
    "soil_depth": "ISRIC SoilGrids 250 m & National NBSS&LUP",
    "lithology": "CGWB Observation Wells Litholog Dataset",
    "rainfall": f"CHIRPS Daily v2.0, {RAIN_START}-{RAIN_END}",
    "ndvi": "Copernicus Sentinel-2 L2A, Cloud Score+ masked",
}

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("mapdata")
MANIFEST: dict = {}


# =====================================================================
# HELPERS
# =====================================================================
def init_ee(project: str | None) -> None:
    proj = project or GEE_PROJECT
    try:
        ee.Initialize(project=proj)
        log.info("Initialized Earth Engine with project: %s", proj)
    except Exception as e:
        log.warning("Earth Engine initialize prompt/authenticate: %s", e)
        ee.Authenticate()
        ee.Initialize(project=proj)
        log.info("Earth Engine authenticated and initialized successfully.")


def tdir(theme: str) -> Path:
    d = OUT_DIR / theme
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_aoi():
    """Return (ee.Geometry EPSG:4326, GeoDataFrame EPSG:4326 per-block)."""
    aoi_path = Path(AOI_VECTOR)
    if not aoi_path.exists():
        # Try finding in map_data/aoi or run prepare_aoi
        alt = BASE_DIR / "map_data" / "aoi" / "aoi_blocks.gpkg"
        if alt.exists():
            aoi_path = alt
        else:
            log.info("AOI file not found. Running prepare_aoi...")
            from src.prepare_aoi import extract_and_save_aoi
            extract_and_save_aoi()
            aoi_path = alt

    gdf = gpd.read_file(aoi_path)
    if gdf.crs is None:
        gdf = gdf.set_crs(4326)
    gdf = gdf.to_crs(4326)

    names = {n.lower() for n in AOI_NAMES}
    sel = gdf[gdf[AOI_NAME_FIELD].astype(str).str.strip().str.lower().isin(names)]
    if not sel.empty:
        gdf = sel.copy().reset_index(drop=True)

    tdir("aoi")
    gdf.to_file(tdir("aoi") / "aoi_blocks.gpkg", driver="GPKG")
    gdf.to_file(tdir("aoi") / "aoi_blocks.geojson", driver="GeoJSON")

    geom = gdf.dissolve().geometry.iloc[0].simplify(0.0003)
    aoi = ee.Geometry(json.loads(json.dumps(mapping(geom))), "EPSG:4326", False)
    area_km2 = gdf.to_crs(UTM_CRS).area.sum() / 1e6
    log.info("AOI Loaded: %s | Total Area: %.1f km²", list(gdf[AOI_NAME_FIELD]), area_km2)
    return aoi, gdf


def export_image(img, theme: str, name: str, region, scale: float, clip=None, crs: str = UTM_CRS):
    """
    Robust image exporter:
    Tries single-request direct export via geemap.ee_export_image.
    If image exceeds the 50 MB GEE limit, automatically tiles into grid chunks and merges seamlessly.
    """
    if clip is not None:
        img = img.clip(clip)
    out = tdir(theme) / f"{name}.tif"
    if out.exists() and out.stat().st_size > 1000:
        log.info("Already exists: %s (%.2f MB), skipping download.", out.name, out.stat().st_size / 1e6)
        return out

    if EXPORT_MODE == "drive":
        task = ee.batch.Export.image.toDrive(
            image=img, description=f"{theme}_{name}", folder=DRIVE_FOLDER,
            fileNamePrefix=f"{theme}_{name}", region=region, scale=scale,
            crs=crs, maxPixels=1e13
        )
        task.start()
        log.info("Drive task submitted: %s_%s", theme, name)
        return out

    log.info("Downloading %s (scale: %sm, crs: %s)...", out.name, scale, crs)
    try:
        geemap.ee_export_image(img, filename=str(out), scale=scale, region=region, crs=crs)
        if out.exists() and out.stat().st_size > 1000:
            log.info("Exported successfully: %s (%.2f MB)", out.name, out.stat().st_size / 1e6)
            return out
    except Exception as e:
        log.warning("Direct export exceeded GEE request limits (%s). Initiating tiled grid export...", e)

    # Tiled Grid Export Fallback
    try:
        # Get bounding box in UTM metric coordinates
        gdf_aoi = gpd.read_file(tdir("aoi") / "aoi_blocks.gpkg").to_crs(crs)
        minx, miny, maxx, maxy = gdf_aoi.total_bounds
        tile_size = 25000.0  # 25 km tiles
        nx = int(math.ceil((maxx - minx) / tile_size))
        ny = int(math.ceil((maxy - miny) / tile_size))

        temp_tiles = []
        for i in range(nx):
            for j in range(ny):
                b_minx = minx + i * tile_size
                b_maxx = min(maxx, b_minx + tile_size)
                b_miny = miny + j * tile_size
                b_maxy = min(maxy, b_miny + tile_size)
                b_box = box(b_minx, b_miny, b_maxx, b_maxy)
                if not gdf_aoi.intersects(b_box).any():
                    continue

                b_gdf = gpd.GeoDataFrame({"geometry": [b_box]}, crs=crs).to_crs("EPSG:4326")
                ee_box = ee.Geometry(json.loads(b_gdf.to_json())["features"][0]["geometry"])
                t_path = tdir(theme) / f"_temp_tile_{name}_{i}_{j}.tif"
                geemap.ee_export_image(img, filename=str(t_path), scale=scale, region=ee_box, crs=crs)
                if t_path.exists() and t_path.stat().st_size > 0:
                    temp_tiles.append(t_path)

        if not temp_tiles:
            raise RuntimeError(f"No tiles successfully downloaded for {name}")

        srcs = [rasterio.open(p) for p in temp_tiles]
        mosaic, trans = merge(srcs)
        meta = srcs[0].meta.copy()
        meta.update({"height": mosaic.shape[1], "width": mosaic.shape[2], "transform": trans, "compress": "deflate"})
        with rasterio.open(out, "w", **meta) as dst:
            dst.write(mosaic)
        for s in srcs:
            s.close()
        for p in temp_tiles:
            p.unlink(missing_ok=True)

        log.info("Tiled export and merge completed: %s (%.2f MB)", out.name, out.stat().st_size / 1e6)
    except Exception as exc:
        log.error("Tiled export failed for %s: %s", name, exc)
        raise

    return out


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def get_dem():
    """Retrieve Copernicus GLO-30 DEM, falling back if needed."""
    try:
        col = ee.ImageCollection("COPERNICUS/DEM/GLO30_2024_1").select("DEM")
        if col.size().getInfo() > 0:
            return col.mosaic().select("DEM").rename("elevation")
    except Exception:
        pass
    try:
        col = ee.ImageCollection("COPERNICUS/DEM/GLO30").select("DEM")
        return col.mosaic().select("DEM").rename("elevation")
    except Exception:
        return ee.Image("USGS/SRTMGL1_003").select("elevation")


# =====================================================================
# THEME IMPLEMENTATIONS
# =====================================================================

# ----------------- 1. DEM & CONTOURS -----------------
def theme_dem(aoi, gdf):
    log.info("Processing Copernicus DEM (30m) & Hydrology Buffer...")
    dem = get_dem()
    export_image(dem, "dem", "dem_aoi", aoi, DEM_SCALE, clip=aoi)
    
    buf_box = aoi.buffer(DEM_BUFFER_M).bounds()
    export_image(dem, "dem", "dem_buffered", buf_box, DEM_SCALE)
    MANIFEST["dem"] = {"source": SOURCES["dem"], "scale_m": DEM_SCALE, "crs": UTM_CRS}
    
    if EXPORT_MODE == "local":
        make_contours(gdf)


def make_contours(gdf):
    import contourpy
    from shapely.geometry import LineString
    src_path = tdir("dem") / "dem_buffered.tif"
    if not src_path.exists():
        log.warning("dem_buffered.tif not found, skipping contours.")
        return

    log.info("Generating 10m contours and 50m index contours...")
    with rasterio.open(src_path) as src:
        z = src.read(1).astype("float64")
        t, crs = src.transform, src.crs
        if src.nodata is not None:
            z[z == src.nodata] = np.nan

    if CONTOUR_SMOOTH_SIGMA > 0:
        try:
            from scipy.ndimage import gaussian_filter
            w = np.isfinite(z).astype(float)
            z = gaussian_filter(np.nan_to_num(z), CONTOUR_SMOOTH_SIGMA) / np.maximum(
                gaussian_filter(w, CONTOUR_SMOOTH_SIGMA), 1e-6)
        except ImportError:
            log.warning("scipy missing: contours unsmoothed")

    h, w_ = z.shape
    x = t.c + (np.arange(w_) + 0.5) * t.a
    y = (t.f + (np.arange(h) + 0.5) * t.e)[::-1]
    zz = np.ma.masked_invalid(z[::-1, :])
    gen = contourpy.contour_generator(x, y, zz, line_type=contourpy.LineType.Separate)
    lo = np.floor(np.nanmin(z) / CONTOUR_INTERVAL) * CONTOUR_INTERVAL
    hi = np.nanmax(z) + CONTOUR_INTERVAL

    rows = []
    for lev in np.arange(lo, hi, CONTOUR_INTERVAL):
        for line in gen.lines(lev):
            if len(line) >= 2:
                rows.append({
                    "elev_m": float(lev),
                    "is_index": int(lev % CONTOUR_INDEX_EVERY == 0),
                    "geometry": LineString(line)
                })

    cdf = gpd.GeoDataFrame(rows, crs=crs)
    cdf = gpd.clip(cdf, gdf.to_crs(crs))
    out_gpkg = tdir("dem") / f"contours_{CONTOUR_INTERVAL}m.gpkg"
    out_geojson = tdir("dem") / f"contours_{CONTOUR_INTERVAL}m.geojson"
    cdf.to_file(out_gpkg, driver="GPKG")
    cdf.to_file(out_geojson, driver="GeoJSON")
    log.info("Contours generated: %d lines saved to %s", len(cdf), out_gpkg.name)


# ----------------- 2. SLOPE -----------------
def theme_slope(aoi, gdf):
    dem_path = tdir("dem") / "dem_aoi.tif"
    if not dem_path.exists():
        theme_dem(aoi, gdf)

    log.info("Computing Slope (Degrees & Percent) from DEM...")
    out_tif = tdir("slope") / "slope_deg_pct.tif"
    with rasterio.open(dem_path) as src:
        dem_arr = src.read(1).astype("float32")
        nd = src.nodata
        res_x = abs(src.transform.a)
        res_y = abs(src.transform.e)

        # Gradient
        gy, gx = np.gradient(dem_arr, res_y, res_x)
        slope_rad = np.arctan(np.sqrt(gx ** 2 + gy ** 2))
        slope_deg = np.degrees(slope_rad)
        slope_pct = np.tan(slope_rad) * 100.0

        if nd is not None:
            slope_deg[dem_arr == nd] = -9999
            slope_pct[dem_arr == nd] = -9999

        meta = src.meta.copy()
        meta.update({"count": 2, "dtype": "float32", "nodata": -9999, "compress": "deflate"})
        with rasterio.open(out_tif, "w", **meta) as dst:
            dst.write(slope_deg.astype("float32"), 1)
            dst.write(slope_pct.astype("float32"), 2)
            dst.set_band_description(1, "slope_degrees")
            dst.set_band_description(2, "slope_percent")

    MANIFEST["slope"] = {"bands": ["slope_deg", "slope_pct"], "source": SOURCES["slope"], "file": str(out_tif)}
    log.info("Slope exported: %s", out_tif.name)


# ----------------- 3. STREAMS (3KM² HIGHEST THRESHOLD) -----------------
def theme_streams(aoi, gdf):
    log.info("Processing Hydrological Streams (Threshold: %.1f km²)...", STREAM_THRESHOLD_KM2)
    try:
        from whitebox import WhiteboxTools
    except ImportError:
        log.error("WhiteboxTools is required for stream extraction. Run: pip install whitebox")
        return

    dem_path = tdir("dem") / "dem_buffered.tif"
    if not dem_path.exists():
        theme_dem(aoi, gdf)

    d = (tdir("streams")).resolve()
    f = lambda n: str(d / n)
    with rasterio.open(dem_path) as src:
        res, crs = abs(src.res[0]), src.crs
        arr = src.read(1)
        meta = src.meta.copy()
        meta.update({'compress': 'deflate', 'dtype': 'float32', 'nodata': src.nodata})
        dem_clean = d / "dem_for_wbt.tif"
        with rasterio.open(dem_clean, 'w', **meta) as dst:
            dst.write(arr.astype('float32'), 1)
    
    # 3.0 km2 threshold calculation
    thr = int(STREAM_THRESHOLD_KM2 * 1e6 / (res ** 2))
    log.info("Hydro stream threshold: %d cells (%.2f km² contributing drainage area)", thr, STREAM_THRESHOLD_KM2)

    wbt = WhiteboxTools()
    wbt.verbose = False
    wbt.fill_depressions(str(dem_clean), f("dem_filled.tif"), fix_flats=True)
    wbt.d8_pointer(f("dem_filled.tif"), f("d8_ptr.tif"))
    wbt.d8_flow_accumulation(f("d8_ptr.tif"), f("flowacc.tif"), out_type="cells", pntr=True)
    wbt.extract_streams(f("flowacc.tif"), f("streams.tif"), threshold=thr, zero_background=True)
    wbt.strahler_stream_order(f("d8_ptr.tif"), f("streams.tif"), f("strahler.tif"), zero_background=True)
    wbt.raster_streams_to_vector(f("strahler.tif"), f("d8_ptr.tif"), f("streams_raw.shp"))

    s = gpd.read_file(f("streams_raw.shp")).set_crs(crs, allow_override=True)
    col = next((c for c in s.columns if c.upper() in ("STRM_VAL", "VALUE", "STRAHLER")), None)
    if col is None:
        col = next(c for c in s.columns if c != "geometry" and np.issubdtype(s[c].dtype, np.number))
    s = s.rename(columns={col: "strahler"})[["strahler", "geometry"]]
    s["strahler"] = s["strahler"].astype(int)
    
    aoi_u = gdf.to_crs(crs)
    s = gpd.clip(s, aoi_u)
    s["len_km"] = (s.length / 1000.0).round(3)
    
    # Export All Strahler Streams
    out_all_gpkg = d / "streams_strahler.gpkg"
    out_all_geojson = d / "streams_strahler.geojson"
    s.to_file(out_all_gpkg, driver="GPKG")
    s.to_file(out_all_geojson, driver="GeoJSON")

    # Order summary table
    summ = s.groupby("strahler").agg(segment_count=("len_km", "size"), total_length_km=("len_km", "sum")).reset_index()
    summ["total_length_km"] = summ["total_length_km"].round(2)
    write_csv(d / "stream_order_summary.csv", summ.to_dict("records"))

    # Extract HIGHEST stream orders (highest Strahler orders)
    max_order = int(s["strahler"].max())
    highest_threshold_order = max(max_order - 1, 3) if max_order >= 4 else max_order
    highest_streams = s[s["strahler"] >= highest_threshold_order].copy()
    highest_streams.to_file(d / "streams_highest_orders.gpkg", driver="GPKG")
    highest_streams.to_file(d / "streams_highest_orders.geojson", driver="GeoJSON")
    log.info("Highest Order Streams (Orders >= %d, Max: %d): %d segments saved",
             highest_threshold_order, max_order, len(highest_streams))

    # Drainage density grid (1 km cells)
    minx, miny, maxx, maxy = aoi_u.total_bounds
    cells = [box(x, y, x + DD_CELL_M, y + DD_CELL_M)
             for x in np.arange(minx, maxx, DD_CELL_M) for y in np.arange(miny, maxy, DD_CELL_M)]
    grid = gpd.GeoDataFrame({"gid": range(len(cells))}, geometry=cells, crs=crs)
    grid = gpd.overlay(grid, aoi_u[["geometry"]], how="intersection")
    grid["area_km2"] = grid.area / 1e6
    grid = grid[grid.area_km2 > 0.05 * (DD_CELL_M / 1000) ** 2].copy()
    inter = gpd.overlay(s[["geometry"]], grid[["gid", "geometry"]], how="intersection")
    ln = (inter.length / 1000).groupby(inter["gid"]).sum()
    grid["stream_km"] = grid["gid"].map(ln).fillna(0).round(2)
    grid["dd_km_per_km2"] = (grid["stream_km"] / grid["area_km2"]).round(3)
    grid.to_file(d / "drainage_density_grid.gpkg", driver="GPKG")
    grid.to_file(d / "drainage_density_grid.geojson", driver="GeoJSON")

    aoi_area = aoi_u.area.sum() / 1e6
    overall_dd = s["len_km"].sum() / aoi_area
    MANIFEST["streams"] = {
        "threshold_km2": STREAM_THRESHOLD_KM2,
        "max_strahler_order": max_order,
        "overall_dd_km_per_km2": round(overall_dd, 3),
        "source": SOURCES["streams"]
    }
    log.info("Streams completed: Max Order: %d | Drainage Density: %.2f km/km²", max_order, overall_dd)


# ----------------- 4. LULC (ESRI 10M) -----------------
def theme_lulc(aoi, gdf):
    log.info("Fetching Esri 10m Annual LULC...")
    col = ee.ImageCollection(ESRI_LULC_ASSET)
    used, sub = None, None
    for y in range(LULC_YEAR, LULC_YEAR - 5, -1):
        sub = col.filterDate(f"{y}-01-01", f"{y + 1}-01-01").filterBounds(aoi)
        if sub.size().getInfo() > 0:
            used = y
            break
    if used is None:
        raise RuntimeError("No Esri LULC year found in collection.")
    
    lulc = sub.mosaic().select(0).rename("lulc").toByte()
    out_tif = export_image(lulc, "lulc", f"lulc_esri_{used}", aoi, LULC_SCALE, clip=aoi)

    # Compute area breakdown
    res = (ee.Image.pixelArea().divide(1e4).addBands(lulc)
           .reduceRegion(ee.Reducer.sum().group(1, "class"), aoi, LULC_SCALE, maxPixels=1e11, tileScale=8)
           .getInfo())
    rows = []
    for g in res["groups"]:
        c = int(g["class"])
        name, color = LEGENDS["lulc_esri"].get(c, ("Unknown", "#000000"))
        rows.append({"class": c, "name": name, "hex": color, "area_ha": round(g["sum"], 1)})
    tot = sum(r["area_ha"] for r in rows)
    for r in rows:
        r["pct"] = round(100.0 * r["area_ha"] / tot, 2) if tot > 0 else 0
    write_csv(tdir("lulc") / f"lulc_{used}_area_table.csv", sorted(rows, key=lambda r: r["class"]))
    MANIFEST["lulc"] = {"year_used": used, "source": SOURCES["lulc"], "file": str(out_tif)}
    log.info("LULC completed for year %d.", used)


# ----------------- 5. RAINFALL (CHIRPS 1991-2024) -----------------
def theme_rainfall(aoi, gdf):
    log.info("Processing CHIRPS Rainfall (%d-%d)...", RAIN_START, RAIN_END)
    chirps = ee.ImageCollection("UCSB-CHG/CHIRPS/DAILY").select("precipitation")
    imgs = []
    for y in range(RAIN_START, RAIN_END + 1):
        bands = [chirps.filterDate(f"{y}-01-01", f"{y + 1}-01-01").sum().rename("annual")]
        for s, (m1, m2) in SEASONS.items():
            ey, em = (y + 1, 1) if m2 == 13 else (y, m2)
            bands.append(chirps.filterDate(f"{y}-{m1:02d}-01", f"{ey}-{em:02d}-01").sum().rename(s))
        imgs.append(ee.Image.cat(bands).set("year", y))
    col = ee.ImageCollection.fromImages(imgs)

    mean = col.mean()
    std = col.reduce(ee.Reducer.stdDev())
    cv = std.divide(mean.rename(std.bandNames())).multiply(100).rename(mean.bandNames())
    trend = (col.select("annual")
             .map(lambda i: ee.Image.constant(ee.Number(i.get("year"))).float().rename("t").addBands(i))
             .select(["t", "annual"]).reduce(ee.Reducer.linearFit()).select("scale").rename("trend_mm_per_yr"))

    export_image(mean, "rainfall", f"rain_mean_mm_{RAIN_START}_{RAIN_END}", aoi, RAIN_SCALE, clip=aoi)
    export_image(cv, "rainfall", "rain_cv_pct", aoi, RAIN_SCALE, clip=aoi)
    export_image(trend, "rainfall", "rain_annual_trend_mm_per_yr", aoi, RAIN_SCALE, clip=aoi)

    # Time series CSV
    fc = ee.FeatureCollection(col.map(
        lambda i: ee.Feature(None, i.reduceRegion(ee.Reducer.mean(), aoi, RAIN_SCALE).set("year", i.get("year")))))
    features = fc.getInfo()["features"]
    rows = [f["properties"] for f in features]
    rows = sorted(rows, key=lambda r: r["year"])
    write_csv(tdir("rainfall") / "rain_timeseries_aoi_mean_mm.csv",
              [{k: (round(v, 1) if k != "year" and v is not None else v) for k, v in r.items()} for r in rows])
    MANIFEST["rainfall"] = {"years": [RAIN_START, RAIN_END], "source": SOURCES["rainfall"]}
    log.info("Rainfall statistics and time series exported.")


# ----------------- 6. NDVI (SENTINEL-2 + CLOUD SCORE+) -----------------
def theme_ndvi(aoi, gdf):
    log.info("Processing Sentinel-2 NDVI with Cloud Score+ masking...")
    cs = ee.ImageCollection("GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED")

    def build_composite(start, end, red):
        c = (ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED").filterBounds(aoi).filterDate(start, end)
             .linkCollection(cs, ["cs_cdf"])
             .map(lambda i: i.updateMask(i.select("cs_cdf").gte(CS_THRESHOLD))
                  .normalizedDifference(["B8", "B4"]).rename("NDVI")))
        return (c.mean() if red == "mean" else c.median()).rename("NDVI")

    for name, (a, b, red) in NDVI_PERIODS.items():
        log.info("Exporting NDVI %s (%s to %s)...", name, a, b)
        comp = build_composite(a, b, red)
        export_image(comp, "ndvi", f"ndvi_{name}_{a[:7]}_{b[:7]}", aoi, NDVI_SCALE, clip=aoi)

    MANIFEST["ndvi"] = {"periods": NDVI_PERIODS, "cloud_score_min": CS_THRESHOLD, "source": SOURCES["ndvi"]}
    log.info("NDVI composites exported.")


# ----------------- 7. ROADS (OSM) -----------------
def theme_roads(aoi, gdf):
    import osmnx as ox
    ox.settings.requests_timeout = 180
    poly = gdf.dissolve().geometry.iloc[0]
    log.info("Fetching roads from OpenStreetMap within AOI...")
    feats = ox.features_from_polygon(poly, tags={"highway": True}).reset_index()
    feats = feats[feats.geometry.type.isin(["LineString", "MultiLineString"])].copy()
    cls = {
        "motorway": "Trunk/Motorway", "motorway_link": "Trunk/Motorway", "trunk": "Trunk/Motorway",
        "trunk_link": "Trunk/Motorway", "primary": "Primary", "primary_link": "Primary",
        "secondary": "Secondary", "secondary_link": "Secondary", "tertiary": "Tertiary",
        "tertiary_link": "Tertiary", "residential": "Residential/Unclassified",
        "unclassified": "Residential/Unclassified", "service": "Residential/Unclassified",
        "track": "Track/Path", "path": "Track/Path", "footway": "Track/Path"
    }
    feats["highway"] = feats["highway"].astype(str)
    feats["road_class"] = feats["highway"].map(cls).fillna("Other")
    keep = [c for c in ["osmid", "highway", "road_class", "name", "ref", "surface", "lanes", "geometry"]
            if c in feats.columns]
    out_gpkg = tdir("roads") / "roads_osm.gpkg"
    out_geojson = tdir("roads") / "roads_osm.geojson"
    feats[keep].to_file(out_gpkg, driver="GPKG")
    feats[keep].to_file(out_geojson, driver="GeoJSON")
    km = feats.to_crs(UTM_CRS).length.sum() / 1000.0
    MANIFEST["roads"] = {"file": str(out_gpkg), "total_km": round(km, 1), "source": SOURCES["roads"]}
    log.info("Roads: %d features, %.1f km saved to %s", len(feats), km, out_gpkg.name)


# ----------------- 8. LITHOLOGY & LOCAL DATA -----------------
def theme_lithology(aoi, gdf):
    log.info("Clipping Litholog observations to AOI...")
    litho_file = Path(LITHOLOGY_SRC)
    if not litho_file.exists():
        log.warning("Litholog dataset not found: %s", litho_file)
        return

    df = gpd.read_file(litho_file)
    if df.crs is None:
        df = df.set_crs(4326)
    df = df.to_crs(gdf.crs)
    clipped = gpd.clip(df, gdf)
    out_gpkg = tdir("lithology") / "lithology.gpkg"
    out_geojson = tdir("lithology") / "lithology.geojson"
    clipped.to_file(out_gpkg, driver="GPKG")
    clipped.to_file(out_geojson, driver="GeoJSON")
    log.info("Litholog: %d observation wells saved to %s", len(clipped), out_gpkg.name)
    MANIFEST["lithology"] = {"file": str(out_gpkg), "count": len(clipped), "source": SOURCES["lithology"]}


def theme_soil_depth(aoi, gdf):
    log.info("Processing Soil Depth...")
    try:
        from process_local_data import process_soil_depth
    except ImportError:
        from src.process_local_data import process_soil_depth
    process_soil_depth(gdf)


# =====================================================================
# THEMES REGISTRY & MAIN
# =====================================================================
THEMES = {
    "dem": theme_dem,
    "slope": theme_slope,
    "streams": theme_streams,
    "lulc": theme_lulc,
    "rainfall": theme_rainfall,
    "ndvi": theme_ndvi,
    "roads": theme_roads,
    "lithology": theme_lithology,
    "soil_depth": theme_soil_depth,
}


def main():
    global OUT_DIR, EXPORT_MODE
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--project", default=GEE_PROJECT, help="Google Cloud project ID with GEE enabled")
    ap.add_argument("--themes", nargs="+", default=["all"], choices=["all"] + list(THEMES))
    ap.add_argument("--out", default=str(OUT_DIR))
    ap.add_argument("--mode", choices=["local", "drive"], default=EXPORT_MODE)
    a = ap.parse_args()

    OUT_DIR = Path(a.out)
    EXPORT_MODE = a.mode
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    init_ee(a.project if a.project != "your-gcp-project-id" else None)
    aoi, gdf = load_aoi()
    todo = list(THEMES) if "all" in a.themes else a.themes

    for t in todo:
        log.info("==================== THEME: %s ====================", t.upper())
        try:
            THEMES[t](aoi, gdf)
        except Exception:
            log.exception("Theme '%s' encountered an error (continuing with remaining themes)", t)

    (OUT_DIR / "legend_specs.json").write_text(json.dumps(LEGENDS, indent=2), encoding="utf-8")
    MANIFEST["_run"] = {
        "date": datetime.now().isoformat(timespec="seconds"),
        "mode": EXPORT_MODE,
        "crs": UTM_CRS,
        "aoi": AOI_NAMES,
        "stream_threshold_km2": STREAM_THRESHOLD_KM2,
    }
    (OUT_DIR / "manifest.json").write_text(json.dumps(MANIFEST, indent=2, default=str), encoding="utf-8")
    log.info("Processing complete! Map data saved in: %s", OUT_DIR.resolve())


if __name__ == "__main__":
    main()

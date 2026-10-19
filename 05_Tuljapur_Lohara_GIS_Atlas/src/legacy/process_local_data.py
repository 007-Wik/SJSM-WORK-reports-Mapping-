import csv
import json
import logging
from pathlib import Path
import geopandas as gpd
import numpy as np
import pyogrio
import rasterio
from rasterio.mask import mask
from rasterio.warp import calculate_default_transform, reproject, Resampling

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("process_local_data")

BASE_DIR = Path(__file__).resolve().parent.parent
UTM_CRS = "EPSG:32643"
OUT_DIR = BASE_DIR / "map_data"
AOI_PATH = OUT_DIR / "aoi" / "aoi_blocks.gpkg"

def get_raw_path(rel_path: str) -> Path:
    p1 = BASE_DIR / "data" / rel_path
    if p1.exists():
        return p1
    p2 = BASE_DIR / rel_path
    if p2.exists():
        return p2
    return Path(rel_path)

def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path

def process_soil_depth(aoi: gpd.GeoDataFrame):
    log.info("=== Processing National Soil Depth Dataset ===")
    src_tif = get_raw_path("raw_data/soil_depth/Soil Depth/SOILDEPTH.tif")
    src_dbf = get_raw_path("raw_data/soil_depth/Soil Depth/SOILDEPTH.tif.vat.dbf")
    out_dir = ensure_dir(OUT_DIR / "soil_depth")
    out_tif = out_dir / "soildepth_aoi_utm.tif"
    out_csv = out_dir / "soildepth_area_summary.csv"
    
    if not src_tif.exists():
        log.warning("Soil depth source TIF not found: %s", src_tif)
        return

    # Read VAT attribute table
    vat_df = pyogrio.read_dataframe(src_dbf)
    # Mapping dictionary
    class_map = {}
    color_map = {}
    for _, r in vat_df.iterrows():
        v = int(r["value"])
        class_name = str(r["class"]).strip()
        r_c = int(float(r["red"]) * 255)
        g_c = int(float(r["green"]) * 255)
        b_c = int(float(r["blue"]) * 255)
        hex_color = f"#{r_c:02x}{g_c:02x}{b_c:02x}"
        class_map[v] = class_name
        color_map[v] = hex_color

    with rasterio.open(src_tif) as src:
        aoi_src_crs = aoi.to_crs(src.crs)
        geoms = [aoi_src_crs.geometry.union_all()]
        
        # Mask / Crop to AOI
        masked_img, masked_transform = mask(src, geoms, crop=True, nodata=255)
        
        # Reproject to UTM 43N
        transform, width, height = calculate_default_transform(
            src.crs, UTM_CRS, masked_img.shape[2], masked_img.shape[1],
            *rasterio.transform.array_bounds(masked_img.shape[1], masked_img.shape[2], masked_transform),
            resolution=(50.0, 50.0) # 50m metric grid
        )
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': UTM_CRS,
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': 255,
            'dtype': 'uint8',
            'compress': 'deflate'
        })
        
        reprojected_arr = np.full((1, height, width), 255, dtype=np.uint8)
        
        reproject(
            source=masked_img,
            destination=reprojected_arr,
            src_transform=masked_transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=UTM_CRS,
            resampling=Resampling.nearest,
            src_nodata=255,
            dst_nodata=255
        )
        
        # Mask strictly to UTM AOI boundary
        aoi_utm = aoi.to_crs(UTM_CRS)
        from rasterio.features import geometry_mask
        inside = geometry_mask([aoi_utm.geometry.union_all()], out_shape=(height, width), transform=transform, invert=True)
        reprojected_arr[0][~inside] = 255
        
        with rasterio.open(out_tif, 'w', **kwargs) as dst:
            dst.write(reprojected_arr)
            
    # Calculate area statistics
    valid_pixels = reprojected_arr[0][reprojected_arr[0] != 255]
    vals, counts = np.unique(valid_pixels, return_counts=True)
    pixel_area_ha = (50.0 * 50.0) / 10000.0 # 0.25 ha per pixel
    total_area_ha = len(valid_pixels) * pixel_area_ha
    
    rows = []
    for v, cnt in zip(vals, counts):
        v = int(v)
        c_name = class_map.get(v, f"Class {v}")
        c_hex = color_map.get(v, "#888888")
        area_ha = round(cnt * pixel_area_ha, 1)
        pct = round(100.0 * area_ha / total_area_ha, 2)
        rows.append({
            "value": v,
            "class_name": c_name,
            "hex_color": c_hex,
            "area_ha": area_ha,
            "pct": pct
        })
        
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["value", "class_name", "hex_color", "area_ha", "pct"])
        w.writeheader()
        w.writerows(rows)
        
    log.info("Saved Soil Depth GeoTIFF to %s", out_tif)
    log.info("Saved Soil Depth Area Table to %s", out_csv)

def process_lulc_250k(aoi: gpd.GeoDataFrame):
    log.info("=== Processing National LULC 250k (2016-2017) Dataset ===")
    src_tif = get_raw_path("raw_data/lulc250k/LULC 250k 1617/lulc250k_1617.tif")
    src_dbf = get_raw_path("raw_data/lulc250k/LULC 250k 1617/lulc250k_1617.tif.vat.dbf")
    out_dir = ensure_dir(OUT_DIR / "lulc")
    out_tif = out_dir / "lulc250k_1617_aoi_utm.tif"
    out_csv = out_dir / "lulc250k_1617_area_table.csv"
    
    if not src_tif.exists():
        log.warning("LULC source TIF not found: %s", src_tif)
        return

    vat_df = pyogrio.read_dataframe(src_dbf)
    class_map = {}
    level1_map = {}
    color_map = {}
    for _, r in vat_df.iterrows():
        v = int(r["value"])
        class_name = str(r["level_3"]).strip()
        l1 = str(r["level_1"]).strip()
        r_c = int(r["red"])
        g_c = int(r["green"])
        b_c = int(r["blue"])
        class_map[v] = class_name
        level1_map[v] = l1
        color_map[v] = f"#{r_c:02x}{g_c:02x}{b_c:02x}"

    with rasterio.open(src_tif) as src:
        aoi_src_crs = aoi.to_crs(src.crs)
        geoms = [aoi_src_crs.geometry.union_all()]
        
        masked_img, masked_transform = mask(src, geoms, crop=True, nodata=255)
        
        transform, width, height = calculate_default_transform(
            src.crs, UTM_CRS, masked_img.shape[2], masked_img.shape[1],
            *rasterio.transform.array_bounds(masked_img.shape[1], masked_img.shape[2], masked_transform),
            resolution=(50.0, 50.0)
        )
        
        kwargs = src.meta.copy()
        kwargs.update({
            'crs': UTM_CRS,
            'transform': transform,
            'width': width,
            'height': height,
            'nodata': 255,
            'dtype': 'uint8',
            'compress': 'deflate'
        })
        
        reprojected_arr = np.full((1, height, width), 255, dtype=np.uint8)
        
        reproject(
            source=masked_img,
            destination=reprojected_arr,
            src_transform=masked_transform,
            src_crs=src.crs,
            dst_transform=transform,
            dst_crs=UTM_CRS,
            resampling=Resampling.nearest,
            src_nodata=255,
            dst_nodata=255
        )
        
        aoi_utm = aoi.to_crs(UTM_CRS)
        from rasterio.features import geometry_mask
        inside = geometry_mask([aoi_utm.geometry.union_all()], out_shape=(height, width), transform=transform, invert=True)
        reprojected_arr[0][~inside] = 255
        
        with rasterio.open(out_tif, 'w', **kwargs) as dst:
            dst.write(reprojected_arr)

    valid_pixels = reprojected_arr[0][reprojected_arr[0] != 255]
    vals, counts = np.unique(valid_pixels, return_counts=True)
    pixel_area_ha = (50.0 * 50.0) / 10000.0
    total_area_ha = len(valid_pixels) * pixel_area_ha
    
    rows = []
    for v, cnt in zip(vals, counts):
        v = int(v)
        c_name = class_map.get(v, f"Class {v}")
        l1 = level1_map.get(v, "")
        c_hex = color_map.get(v, "#888888")
        area_ha = round(cnt * pixel_area_ha, 1)
        pct = round(100.0 * area_ha / total_area_ha, 2)
        rows.append({
            "value": v,
            "category": l1,
            "class_name": c_name,
            "hex_color": c_hex,
            "area_ha": area_ha,
            "pct": pct
        })
        
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["value", "category", "class_name", "hex_color", "area_ha", "pct"])
        w.writeheader()
        w.writerows(rows)
        
    log.info("Saved LULC 250k GeoTIFF to %s", out_tif)
    log.info("Saved LULC 250k Area Table to %s", out_csv)

def process_litholog(aoi: gpd.GeoDataFrame):
    log.info("=== Processing Litholog / Hydrogeology Well Dataset ===")
    src_file = get_raw_path("Litholog.geojson")
    out_dir = ensure_dir(OUT_DIR / "lithology")
    
    if not src_file.exists():
        log.warning("Litholog.geojson not found")
        return
        
    litho = gpd.read_file(src_file)
    aoi_utm = aoi.to_crs(UTM_CRS)
    aoi_geom = aoi_utm.geometry.union_all()
    
    litho_utm = litho.to_crs(UTM_CRS)
    litho_utm["dist_km"] = litho_utm.geometry.distance(aoi_geom) / 1000.0
    
    # Save wells within regional catchment / buffer (50 km from AOI)
    nearby_wells = litho_utm[litho_utm["dist_km"] <= 50.0].sort_values("dist_km").reset_index(drop=True)
    out_gpkg = out_dir / "cgwb_litholog_regional_wells_50km.gpkg"
    nearby_wells.to_file(out_gpkg, driver="GPKG")
    
    # Summary of lithologies in regional surrounding area
    summary = nearby_wells.groupby("Major_Lithology").agg(
        num_wells=("GmlID", "count"),
        min_dist_km=("dist_km", "min"),
        mean_dist_km=("dist_km", "mean")
    ).reset_index()
    summary["min_dist_km"] = summary["min_dist_km"].round(1)
    summary["mean_dist_km"] = summary["mean_dist_km"].round(1)
    summary.to_csv(out_dir / "regional_lithology_summary.csv", index=False)
    
    log.info("Saved %d nearby litholog/borewell points (within 50 km) to %s", len(nearby_wells), out_gpkg)

def main():
    if not AOI_PATH.exists():
        log.error("AOI file not found at %s. Please run prepare_aoi.py first.", AOI_PATH)
        return
    aoi = gpd.read_file(AOI_PATH)
    process_soil_depth(aoi)
    process_lulc_250k(aoi)
    process_litholog(aoi)
    log.info("All local dataset processing finished successfully!")

if __name__ == "__main__":
    main()

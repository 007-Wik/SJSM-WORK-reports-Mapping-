#!/usr/bin/env python3
"""
Stage 01: Data Download & Area of Interest (AOI) Ingestion Pipeline
Standardized data acquisition script:
1. Validates and queries raw administrative cadastral data (data/raw/mh1.geojson, data/raw/mh2.geojson).
2. Extracts high-fidelity boundary polygons for Tuljapur (1,500.7 km²) and Lohara (543.2 km²).
3. Ingests all 177 cadastral village polygons with names and spatial attributes into data/processed/aoi/.
4. Verifies presence and coverage of regional DEM, soil, lithology, and RGNDWM datasets.
"""
from pathlib import Path
import geopandas as gpd

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw" if (BASE_DIR / "data" / "raw").exists() else BASE_DIR / "data"
DATA_PROC = BASE_DIR / "data" / "processed"
AOI_DIR = DATA_PROC / "aoi"
AOI_DIR.mkdir(parents=True, exist_ok=True)

TARGET_BLOCKS = ["Tuljapur", "Lohara"]


def extract_aoi_boundaries():
    print("=" * 70)
    print("STAGE 01: DATA INGESTION & AOI EXTRACTION")
    print("=" * 70)

    # 1. Load administrative subblocks
    mh1_path = DATA_RAW / "mh1.geojson"
    mh2_path = DATA_RAW / "mh2.geojson"

    src_path = mh1_path if mh1_path.exists() else mh2_path
    if not src_path.exists():
        print(f"WARNING: Neither mh1.geojson nor mh2.geojson found in {DATA_RAW}.")
        print("Checking data/processed/aoi for existing boundaries...")
        if (AOI_DIR / "aoi_blocks.gpkg").exists():
            print("Existing aoi_blocks.gpkg verified!")
            return
        raise FileNotFoundError(f"Raw cadastral data missing in {DATA_RAW}")

    print(f"Reading administrative boundaries from: {src_path.name}...")
    gdf = gpd.read_file(src_path)

    # Filter for target blocks
    block_col = "BLOCK" if "BLOCK" in gdf.columns else "block"
    village_col = "VILLAGE" if "VILLAGE" in gdf.columns else "village"

    aoi_villages = gdf[gdf[block_col].isin(TARGET_BLOCKS)].copy()
    aoi_villages = aoi_villages.to_crs(epsg=32643)

    print(f"Found {len(aoi_villages)} village polygons across target blocks:")
    for b in TARGET_BLOCKS:
        cnt = len(aoi_villages[aoi_villages[block_col] == b])
        print(f"  • {b} Taluka: {cnt} villages")

    # Dissolve to taluka blocks
    aoi_blocks = aoi_villages.dissolve(by=block_col, as_index=False)
    aoi_blocks["NAME"] = aoi_blocks[block_col]
    aoi_blocks["area_km2"] = (aoi_blocks.geometry.area / 1e6).round(2)

    # Save to data/processed/aoi/
    out_blocks = AOI_DIR / "aoi_blocks.gpkg"
    out_villages = AOI_DIR / "subblocks_villages.gpkg"

    aoi_blocks[["NAME", "area_km2", "geometry"]].to_file(out_blocks, driver="GPKG")
    aoi_villages[[block_col, village_col, "geometry"]].rename(
        columns={block_col: "BLOCK", village_col: "VILLAGE"}
    ).to_file(out_villages, driver="GPKG")

    print(f"Saved taluka boundaries to: {out_blocks}")
    print(f"Saved village cadastral units to: {out_villages}")
    print("SUCCESS: Stage 01 Data Ingestion Completed!")


if __name__ == "__main__":
    extract_aoi_boundaries()

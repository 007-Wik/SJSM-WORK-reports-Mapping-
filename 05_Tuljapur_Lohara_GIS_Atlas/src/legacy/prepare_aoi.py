import logging
from pathlib import Path
import geopandas as gpd
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("aoi_prep")

def extract_and_save_aoi():
    base_dir = Path(__file__).resolve().parent.parent
    out_dir = base_dir / "map_data" / "aoi"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "aoi_blocks.gpkg"
    
    log.info("Reading mh1.geojson and mh2.geojson...")
    p1 = base_dir / "data" / "mh1.geojson" if (base_dir / "data" / "mh1.geojson").exists() else Path("mh1.geojson")
    p2 = base_dir / "data" / "mh2.geojson" if (base_dir / "data" / "mh2.geojson").exists() else Path("mh2.geojson")
    gdf1 = gpd.read_file(p1)
    gdf2 = gpd.read_file(p2)
    
    # Filter for Osmanabad / Dharashiv and Tuljapur / Lohara sub-districts
    sub1 = gdf1[(gdf1['DISTRICT'].str.lower().fillna('').str.contains('osmanabad')) & (gdf1['SUB_DIST'].isin(['Tuljapur', 'Lohara']))]
    sub2 = gdf2[(gdf2['DISTRICT'].str.lower().fillna('').str.contains('osmanabad')) & (gdf2['SUB_DIST'].isin(['Tuljapur', 'Lohara']))]
    
    log.info(f"Filtered villages - mh1: {len(sub1)}, mh2: {len(sub2)}")
    combined = pd.concat([sub1, sub2], ignore_index=True)
    
    # Select only SUB_DIST and geometry before dissolve to avoid duplicated column names
    combined = combined[['SUB_DIST', 'geometry']]
    
    # Dissolve to Block level
    blocks = combined.dissolve(by='SUB_DIST', as_index=False)
    blocks = blocks.rename(columns={'SUB_DIST': 'NAME'})
    blocks = blocks[['NAME', 'geometry']]
    
    if blocks.crs is None:
        blocks = blocks.set_crs(4326)
    else:
        blocks = blocks.to_crs(4326)
        
    log.info("Calculating block areas (UTM 43N - EPSG:32643)...")
    blocks_utm = blocks.to_crs("EPSG:32643")
    for _, row in blocks_utm.iterrows():
        area_km2 = row['geometry'].area / 1e6
        log.info(f"Block: {row['NAME']} -> Area: {area_km2:.2f} km²")
        
    log.info(f"Saving blocks to {out_file}...")
    blocks.to_file(out_file, driver="GPKG")
    
    # Save village boundaries
    villages = pd.concat([sub1, sub2], ignore_index=True)
    villages = villages.rename(columns={'SUB_DIST': 'BLOCK', 'NAME': 'VILLAGE'})
    villages = gpd.GeoDataFrame(villages[['DISTRICT', 'BLOCK', 'VILLAGE', 'geometry']], geometry='geometry', crs=gdf1.crs)
    villages.to_file(out_dir / "subblocks_villages.gpkg", driver="GPKG")
    villages.to_file(out_dir / "subblocks_villages.geojson", driver="GeoJSON")
    log.info(f"Saved subblocks_villages ({len(villages)} total villages) to {out_dir}")

    # Also save separate GeoJSON
    blocks.to_file(out_dir / "aoi_blocks.geojson", driver="GeoJSON")
    log.info("AOI extraction completed successfully.")

if __name__ == "__main__":
    extract_and_save_aoi()

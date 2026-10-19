import os, glob, math, warnings, traceback
import numpy as np, pandas as pd, geopandas as gpd
import rasterio
from rasterio.crs import CRS
from rasterio.mask import mask as rio_mask
from rasterio.warp import calculate_default_transform, reproject, Resampling
from pyproj import Transformer
from shapely.geometry import mapping
import whitebox

warnings.filterwarnings('ignore')
os.environ["SHAPE_RESTORE_SHX"] = "YES"

# Import the ArcGIS-style renderer
from map_renderer import render_map

# ── CONFIG ───────────────────────────────────────────────────────────────────
TARGET_EPSG = 32643
STREAM_THRESHOLD_FRACTION = 0.0008
CONTOUR_INTERVALS = [5, 10]
NODATA = -9999.0

DEM_PATH = 'Village DEM/PhaltanDEM.tif'
if not os.path.exists(DEM_PATH):
    DEM_PATH = 'Phaltan DEM.tif'
DEM_PATH = os.path.abspath(DEM_PATH)
SHP_FOLDER = os.path.abspath('Selected village/Projected Villages/')
OUTPUT_FOLDER = os.path.abspath('Outputs')

wbt = whitebox.WhiteboxTools()
wbt.verbose = False
wbt.compress_rasters = True
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# ── UTILITIES ────────────────────────────────────────────────────────────────

def safe_remove(*paths):
    for p in paths:
        try:
            if p and os.path.exists(p): os.remove(p)
        except: pass

def reproject_raster(src_path, dst_path, dst_epsg, nodata=NODATA):
    dst_crs = CRS.from_epsg(dst_epsg)
    with rasterio.open(src_path) as src:
        if src.crs and src.crs.to_epsg() == dst_epsg:
            import shutil; shutil.copy(src_path, dst_path); return dst_path
        t, w, h = calculate_default_transform(src.crs, dst_crs, src.width, src.height, *src.bounds)
        meta = src.meta.copy()
        meta.update(crs=dst_crs, transform=t, width=w, height=h, nodata=nodata, compress='lzw', dtype='float32')
        with rasterio.open(dst_path, 'w', **meta) as dst:
            for band in range(1, src.count + 1):
                reproject(source=rasterio.band(src, band), destination=rasterio.band(dst, band),
                          src_transform=src.transform, src_crs=src.crs, dst_transform=t, dst_crs=dst_crs,
                          resampling=Resampling.bilinear, src_nodata=src.nodata, dst_nodata=nodata)
    return dst_path

def reproject_vector(shp_path, dst_epsg):
    gdf = gpd.read_file(shp_path)
    if gdf.crs is None: gdf = gdf.set_crs("EPSG:4326")
    try: current = gdf.crs.to_epsg()
    except: current = None
    if current != dst_epsg: gdf = gdf.to_crs(epsg=dst_epsg)
    return gdf

def clip_raster_to_polygon(raster_path, gdf, out_path, nodata=NODATA, dtype='float32'):
    geoms = [mapping(g) for g in gdf.geometry]
    with rasterio.open(raster_path) as src:
        orig_nodata = src.nodata if src.nodata is not None else nodata
        out_img, out_tf = rio_mask(src, geoms, crop=True, filled=True, nodata=nodata, all_touched=True)
        meta = src.meta.copy()
    out_img = out_img.astype(np.float32)
    out_img[out_img == orig_nodata] = nodata
    out_img[np.isnan(out_img)] = nodata
    out_img[np.isinf(out_img)] = nodata
    meta.update(driver='GTiff', dtype=dtype, nodata=nodata, height=out_img.shape[1], width=out_img.shape[2],
                transform=out_tf, compress='lzw')
    with rasterio.open(out_path, 'w', **meta) as dst:
        dst.write(out_img)
    return out_path

def get_raster_stats(raster_path, nodata=NODATA):
    with rasterio.open(raster_path) as src:
        data = src.read(1).astype(np.float64)
        nd = src.nodata if src.nodata is not None else nodata
    data[data == nd] = np.nan; data[np.isinf(data)] = np.nan
    v = data[~np.isnan(data)]
    if len(v) == 0:
        return dict(min=np.nan, max=np.nan, mean=np.nan, std=np.nan, range=np.nan, count_px=0)
    return dict(min=float(np.nanmin(v)), max=float(np.nanmax(v)), mean=float(np.nanmean(v)),
                std=float(np.nanstd(v)), range=float(np.nanmax(v)-np.nanmin(v)), count_px=len(v))

def area_to_threshold(area_m2, pixel_area_m2, frac=STREAM_THRESHOLD_FRACTION):
    return max(int((area_m2 / pixel_area_m2) * frac), 20)

def preprocess_dem_for_hydro(elev_tif, out_dir):
    p = lambda name: os.path.join(out_dir, f'_hydro_{name}.tif')
    dem_filled = p('01_fill'); wbt.fill_missing_data(elev_tif, dem_filled, filter=11)
    dem_smooth = p('02_smooth'); wbt.feature_preserving_smoothing(dem_filled, dem_smooth, filter=9, norm_diff=8, num_iter=3, max_diff=0.5)
    dem_breach = p('03_breach'); wbt.breach_depressions_least_cost(dem_smooth, dem_breach, dist=10, flat_increment=0.001, fill=True)
    dem_ready  = p('04_fill'); wbt.fill_depressions(dem_breach, dem_ready, fix_flats=True, flat_increment=0.001)
    fdir = p('05_fdir'); wbt.d8_pointer(dem_ready, fdir)
    facc = p('06_facc'); wbt.d8_flow_accumulation(fdir, facc, out_type='cells', pntr=True)
    safe_remove(dem_filled, dem_smooth, dem_breach, dem_ready)
    return fdir, facc

# ── MAIN PIPELINE ────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print("Preparing base DEM...")
    dem_utm = os.path.join(OUTPUT_FOLDER, 'PhaltanDEM_UTM43N.tif')
    reproject_raster(DEM_PATH, dem_utm, TARGET_EPSG)
    
    with rasterio.open(dem_utm) as _s:
        pixel_area_m2 = abs(_s.transform.a) * abs(_s.transform.e)

    shp_files = sorted(glob.glob(os.path.join(SHP_FOLDER, '*.shp')))
    all_stats = []

    for shp_path in shp_files:
        raw = os.path.splitext(os.path.basename(shp_path))[0]
        vname = raw.replace('_prj','').replace('_Prj','').replace('_prjj','').replace('_UTM43N','').strip('_')
        if vname.lower() == 'bodkadewadij':
            vname = 'Bodkewadi'
        
        print(f"\n{'='*60}\n  Processing: {vname}\n{'='*60}")
        vout = os.path.join(OUTPUT_FOLDER, vname)
        os.makedirs(vout, exist_ok=True)
        
        try:
            gdf = reproject_vector(shp_path, TARGET_EPSG)
            if len(gdf) == 0: continue
            village_area_m2 = float(gdf.geometry.area.sum())
            
            # Elevation
            elev_tif = os.path.join(vout, f'{vname}_elevation.tif')
            clip_raster_to_polygon(dem_utm, gdf, elev_tif)
            
            # Slope
            slope_tmp = os.path.join(vout, '_slope_raw.tif')
            slope_tif = os.path.join(vout, f'{vname}_slope.tif')
            wbt.slope(elev_tif, slope_tmp, units='degrees')
            clip_raster_to_polygon(slope_tmp, gdf, slope_tif)
            safe_remove(slope_tmp)
            
            # Stream extraction (buffered DEM)
            buf_m = max(500, math.sqrt(village_area_m2) * 0.3)
            gdf_buf = gdf.copy(); gdf_buf['geometry'] = gdf.geometry.buffer(buf_m)
            elev_buf = os.path.join(vout, '_elev_buf.tif')
            clip_raster_to_polygon(dem_utm, gdf_buf, elev_buf)
            
            fdir, facc = preprocess_dem_for_hydro(elev_buf, vout)
            threshold = area_to_threshold(village_area_m2, pixel_area_m2)
            str_raw = os.path.join(vout, '_str_raw.tif')
            strahler_raw = os.path.join(vout, '_strahler_raw.tif')
            streams_shp = os.path.join(vout, f'{vname}_streams.shp')
            
            wbt.extract_streams(facc, str_raw, threshold=threshold)
            wbt.strahler_stream_order(fdir, str_raw, strahler_raw, esri_pntr=False, zero_background=False)
            
            s_clip = None
            try:
                wbt.raster_streams_to_vector(strahler_raw, fdir, streams_shp, esri_pntr=False)
                s_gdf = gpd.read_file(streams_shp)
                s_gdf = s_gdf.set_crs(epsg=TARGET_EPSG, allow_override=True)
                s_clip = gpd.clip(s_gdf, gdf)
            except Exception as e:
                print(f"    Vectorization warning: {e}")
            
            safe_remove(elev_buf, fdir, facc, str_raw, strahler_raw)

            # Contours
            contour_gdfs = {}
            for interval in CONTOUR_INTERVALS:
                c_shp = os.path.join(vout, f'{vname}_contours_{interval}m.shp')
                try:
                    wbt.contours_from_raster(elev_tif, c_shp, interval=float(interval), base=0.0, smooth=5, tolerance=10.0)
                    c_gdf = gpd.read_file(c_shp)
                    if c_gdf.crs is None: c_gdf = c_gdf.set_crs(epsg=TARGET_EPSG)
                    c_clip = gpd.clip(c_gdf, gdf)
                    c_clip.to_file(c_shp)
                    contour_gdfs[interval] = c_clip
                except Exception as e:
                    print(f"    Contour warning {interval}m: {e}")

            # ── MAP GENERATION (ArcGIS-style) ────────────────────────
            render_map(vname, 'BOUNDARY', gdf,
                       os.path.join(vout, f'{vname}_1_boundary.png'))
            
            render_map(vname, 'ELEVATION', gdf,
                       os.path.join(vout, f'{vname}_2_elevation.png'),
                       raster_path=elev_tif, cmap_name='terrain',
                       label='Elevation', unit='Mtrs')
            
            render_map(vname, 'SLOPE', gdf,
                       os.path.join(vout, f'{vname}_3_slope.png'),
                       raster_path=slope_tif, cmap_name='YlOrRd',
                       label='Slope', unit='Degrees', dem_path=elev_tif)
            
            if s_clip is not None and len(s_clip) > 0:
                render_map(vname, 'STREAM ORDER', gdf,
                           os.path.join(vout, f'{vname}_4_streams.png'),
                           vector_gdf=s_clip)
            
            for interval, c_gdf in contour_gdfs.items():
                render_map(vname, f'CONTOUR ({interval}m)', gdf,
                           os.path.join(vout, f'{vname}_5_contours_{interval}m.png'),
                           vector_gdf=c_gdf, contour_interval=interval)
            
            # Stats
            row = {'Village': vname, 'Area_km2': round(village_area_m2/1e6, 4)}
            for attr, path in [('Elevation', elev_tif), ('Slope', slope_tif)]:
                s = get_raster_stats(path)
                for k, v in s.items(): row[f'{attr}_{k}'] = round(v, 3) if isinstance(v, float) else v
            all_stats.append(row)
            
        except Exception as e:
            print(f"Error processing {vname}: {e}")
            traceback.print_exc()

    if all_stats:
        pd.DataFrame(all_stats).to_csv(os.path.join(OUTPUT_FOLDER, 'village_statistics.csv'), index=False)
        print("All maps and statistics generated successfully!")

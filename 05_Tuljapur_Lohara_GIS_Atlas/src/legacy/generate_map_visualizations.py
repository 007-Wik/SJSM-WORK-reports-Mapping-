#!/usr/bin/env python3
"""
Generate publication-quality cartographic map visualization figures (PNG)
for Tuljapur & Lohara blocks across all thematic layers.
"""
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import rasterio
from rasterio.plot import show

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
MAP_OUT = BASE_DIR / "CLIENT_DELIVERABLES" / "01_Combined_Tuljapur_Lohara" / "09_Map_Visualizations"
MAP_OUT.mkdir(parents=True, exist_ok=True)

# Set global aesthetics
plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = ["DejaVu Sans", "Arial"]

aoi = gpd.read_file(MAP_DATA / "aoi" / "aoi_blocks.gpkg").to_crs("EPSG:32643")

def setup_map_figure(title, subtitle):
    fig, ax = plt.subplots(figsize=(12, 9), dpi=300)
    fig.patch.set_facecolor("#ffffff")
    ax.set_facecolor("#f8f9fa")
    
    # Title & Subtitle banner
    fig.suptitle(title, fontsize=16, fontweight="bold", y=0.96, color="#1e293b")
    ax.set_title(subtitle, fontsize=11, color="#64748b", pad=12)
    
    # Grid & ticks
    ax.grid(True, linestyle="--", alpha=0.4, color="#94a3b8")
    ax.set_xlabel("Easting (m) - UTM Zone 43N", fontsize=9, color="#475569")
    ax.set_ylabel("Northing (m) - UTM Zone 43N", fontsize=9, color="#475569")
    
    return fig, ax

def add_aoi_boundary(ax):
    aoi.boundary.plot(ax=ax, color="#0f172a", linewidth=1.8, linestyle="-", label="Block Boundary", zorder=10)
    # Block labels
    for _, row in aoi.iterrows():
        cent = row.geometry.centroid
        ax.annotate(
            row["NAME"].upper(), xy=(cent.x, cent.y),
            xytext=(0, 0), textcoords="offset points",
            ha="center", va="center", fontsize=11, fontweight="bold",
            color="#0f172a", bbox=dict(boxstyle="round,pad=0.3", fc="#ffffff", ec="#64748b", alpha=0.85),
            zorder=12
        )

# 1. Elevation DEM & Contours Map
def plot_elevation_map():
    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    contours_path = MAP_DATA / "dem" / "contours_10m.gpkg"
    if not dem_path.exists(): return

    fig, ax = setup_map_figure("ELEVATION & TOPOGRAPHY (COPERNICUS GLO-30)", "Tuljapur & Lohara Blocks, Dharashiv District | 10m Contours")
    with rasterio.open(dem_path) as src:
        arr = src.read(1).astype("float32")
        arr[arr == src.nodata] = np.nan
        cmap = plt.cm.terrain
        cmap.set_bad(color="white", alpha=0.0)
        im = ax.imshow(
            arr, extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top],
            cmap=cmap, vmin=np.nanmin(arr), vmax=np.nanmax(arr), zorder=2
        )
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
        cbar.set_label("Elevation Above Sea Level (m)", fontsize=10, fontweight="bold", color="#1e293b")

    if contours_path.exists():
        contours = gpd.read_file(contours_path).to_crs("EPSG:32643")
        index_c = contours[contours["is_index"] == 1]
        regular_c = contours[contours["is_index"] == 0]
        regular_c.plot(ax=ax, color="#78350f", linewidth=0.4, alpha=0.5, zorder=4)
        index_c.plot(ax=ax, color="#451a03", linewidth=0.8, alpha=0.8, zorder=5)

    add_aoi_boundary(ax)
    out_file = MAP_OUT / "Map_01_Elevation_and_Contours.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 2. Slope Map
def plot_slope_map():
    slope_path = MAP_DATA / "slope" / "slope_deg_pct.tif"
    if not slope_path.exists(): return

    fig, ax = setup_map_figure("SLOPE ANALYSIS (DEGREES)", "Tuljapur & Lohara Blocks | Terrain Steepness & Gradient")
    with rasterio.open(slope_path) as src:
        arr = src.read(1).astype("float32")
        arr[arr < 0] = np.nan
        cmap = plt.cm.YlOrRd
        cmap.set_bad(color="white", alpha=0.0)
        im = ax.imshow(
            arr, extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top],
            cmap=cmap, vmin=0, vmax=15, zorder=2
        )
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
        cbar.set_label("Slope (Degrees)", fontsize=10, fontweight="bold", color="#1e293b")

    add_aoi_boundary(ax)
    out_file = MAP_OUT / "Map_02_Slope_Analysis.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 3. Stream Network (3km2 threshold & Highest Strahler Orders)
def plot_streams_map():
    strm_path = MAP_DATA / "streams" / "streams_strahler.gpkg"
    highest_path = MAP_DATA / "streams" / "streams_highest_orders.gpkg"
    if not strm_path.exists(): return

    fig, ax = setup_map_figure("HYDROLOGY & DRAINAGE NETWORK (3 KM² THRESHOLD)", "Strahler Stream Classification (Orders 1 to 4) & Highest Streams Highlighted")
    strm = gpd.read_file(strm_path).to_crs("EPSG:32643")
    
    order_colors = {1: "#93c5fd", 2: "#3b82f6", 3: "#1d4ed8", 4: "#1e3a8a"}
    order_widths = {1: 0.8, 2: 1.4, 3: 2.2, 4: 3.2}

    for order in sorted(strm["strahler"].unique()):
        sub = strm[strm["strahler"] == order]
        sub.plot(
            ax=ax, color=order_colors.get(order, "#2563eb"),
            linewidth=order_widths.get(order, 1.0),
            label=f"Order {order} ({len(sub)} segments, {sub['len_km'].sum():.1f} km)",
            zorder=3 + order
        )

    if highest_path.exists():
        highest = gpd.read_file(highest_path).to_crs("EPSG:32643")
        highest.plot(ax=ax, color="#ef4444", linewidth=1.0, linestyle="--", alpha=0.7, label=f"Highest Orders (≥3, {len(highest)} segments)", zorder=8)

    add_aoi_boundary(ax)
    ax.legend(loc="lower right", frameon=True, framealpha=0.9, facecolor="#ffffff", edgecolor="#cbd5e1", title="Strahler Stream Order")
    out_file = MAP_OUT / "Map_03_Drainage_and_Streams_3km2.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 4. Drainage Density Grid Map
def plot_drainage_density_map():
    dd_path = MAP_DATA / "streams" / "drainage_density_grid.gpkg"
    if not dd_path.exists(): return

    fig, ax = setup_map_figure("DRAINAGE DENSITY GRID (1 KM² CELLS)", "Spatial Concentration of Stream Channels (km / km²)")
    dd = gpd.read_file(dd_path).to_crs("EPSG:32643")
    dd.plot(column="dd_km_per_km2", ax=ax, cmap="Blues", legend=True,
            legend_kwds={"label": "Drainage Density (km / km²)", "orientation": "vertical", "fraction": 0.035, "pad": 0.03},
            edgecolor="#94a3b8", linewidth=0.2, zorder=2)

    add_aoi_boundary(ax)
    out_file = MAP_OUT / "Map_04_Drainage_Density_Grid.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 5. Soil Depth Map
def plot_soil_depth_map():
    soil_path = MAP_DATA / "soil_depth" / "soildepth_aoi_utm.tif"
    if not soil_path.exists(): return

    fig, ax = setup_map_figure("NATIONAL SOIL DEPTH CLASSIFICATION (NBSS&LUP)", "Tuljapur & Lohara Blocks | Metric 50m Resolution")
    with rasterio.open(soil_path) as src:
        arr = src.read(1).astype("float32")
        arr[arr == 255] = np.nan
        cmap = plt.cm.get_cmap("YlOrBr_r", 7)
        cmap.set_bad(color="white", alpha=0.0)
        im = ax.imshow(
            arr, extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top],
            cmap=cmap, zorder=2
        )
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03, ticks=[1, 2, 3, 4, 5, 6, 7])
        cbar.ax.set_yticklabels(["Very Deep (>100cm)", "Deep (50-100cm)", "Mod. Deep (25-50cm)", "Mod. Shallow", "Shallow", "Very Shallow (<10cm)", "Other"], fontsize=8)
        cbar.set_label("Soil Depth Class", fontsize=10, fontweight="bold", color="#1e293b")

    add_aoi_boundary(ax)
    out_file = MAP_OUT / "Map_05_Soil_Depth_Classification.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 6. Road Network Map
def plot_roads_map():
    roads_path = MAP_DATA / "roads" / "roads_osm.gpkg"
    if not roads_path.exists(): return

    fig, ax = setup_map_figure("TRANSPORTATION & ROAD NETWORK (OPENSTREETMAP)", "2,628 km Classified Road Network across Tuljapur & Lohara")
    roads = gpd.read_file(roads_path).to_crs("EPSG:32643")
    
    cls_colors = {
        "Trunk/Motorway": "#dc2626", "Primary": "#ea580c", "Secondary": "#d97706",
        "Tertiary": "#2563eb", "Residential/Unclassified": "#64748b", "Track/Path": "#a1a1aa"
    }
    cls_widths = {
        "Trunk/Motorway": 2.2, "Primary": 1.8, "Secondary": 1.4,
        "Tertiary": 1.0, "Residential/Unclassified": 0.6, "Track/Path": 0.4
    }

    for road_cls in ["Track/Path", "Residential/Unclassified", "Tertiary", "Secondary", "Primary", "Trunk/Motorway"]:
        sub = roads[roads["road_class"] == road_cls]
        if len(sub) > 0:
            sub.plot(
                ax=ax, color=cls_colors.get(road_cls, "#94a3b8"),
                linewidth=cls_widths.get(road_cls, 0.6),
                label=f"{road_cls} ({len(sub)} links, {sub.length.sum()/1000:.0f} km)",
                zorder=3
            )

    add_aoi_boundary(ax)
    ax.legend(loc="lower right", frameon=True, framealpha=0.92, facecolor="#ffffff", edgecolor="#cbd5e1", title="Road Classification")
    out_file = MAP_OUT / "Map_06_Road_Transportation_Network.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 7. Rainfall Map
def plot_rainfall_map():
    rain_path = MAP_DATA / "rainfall" / "rain_mean_mm_1991_2024.tif"
    if not rain_path.exists(): return

    fig, ax = setup_map_figure("MEAN ANNUAL RAINFALL DISTRIBUTION (CHIRPS 1991-2024)", "Long-Term Climatological Mean Precipitation (mm / year)")
    with rasterio.open(rain_path) as src:
        arr = src.read(1).astype("float32")
        cmap = plt.cm.YlGnBu
        im = ax.imshow(
            arr, extent=[src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top],
            cmap=cmap, zorder=2
        )
        cbar = fig.colorbar(im, ax=ax, fraction=0.035, pad=0.03)
        cbar.set_label("Mean Annual Rainfall (mm)", fontsize=10, fontweight="bold", color="#1e293b")

    add_aoi_boundary(ax)
    out_file = MAP_OUT / "Map_07_Annual_Rainfall_Distribution.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

# 8. Lithology & Regional Wells Map
def plot_lithology_map():
    wells_path = MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg"
    if not wells_path.exists(): return

    fig, ax = setup_map_figure("REGIONAL LITHOLOGY & CGWB OBSERVATION WELLS", "Hydrogeology & Bedrock Lithology within 50 km Catchment")
    wells = gpd.read_file(wells_path).to_crs("EPSG:32643")
    
    # Plot wells by Major_Lithology
    for litho_type in wells["Major_Lithology"].unique():
        sub = wells[wells["Major_Lithology"] == litho_type]
        sub.plot(ax=ax, markersize=35, label=f"{litho_type} ({len(sub)} wells)", zorder=4)

    add_aoi_boundary(ax)
    ax.legend(loc="lower right", frameon=True, framealpha=0.9, facecolor="#ffffff", edgecolor="#cbd5e1", title="Observed Lithology")
    out_file = MAP_OUT / "Map_08_Lithology_and_Groundwater_Wells.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)

if __name__ == "__main__":
    print("Generating cartographic map layout visualizations...")
    plot_elevation_map()
    plot_slope_map()
    plot_streams_map()
    plot_drainage_density_map()
    plot_soil_depth_map()
    plot_roads_map()
    plot_rainfall_map()
    plot_lithology_map()
    print("All cartographic map visualizations completed in:", MAP_OUT)

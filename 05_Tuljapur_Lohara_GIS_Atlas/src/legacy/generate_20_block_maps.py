#!/usr/bin/env python3
"""
Complete GIS Map Production Engine for Dharashiv (Osmanabad) District Blocks:
- Tuljapur (Landscape: 20" x 15" @ 300 DPI)
- Lohara (Vertical / Portrait: 15" x 20" @ 300 DPI)

Strict Layout Specifications requested by User:
1. Title INSIDE the mapping panel at the top center:
   - Line 1: Theme Name (e.g. CONTOUR MAP OF, LULC MAP OF) - Times New Roman
   - Line 2: TALUKA NAME (e.g. TULJAPUR / LOHARA) - Times New Roman Bold
   - Subtitle: DISTRICT DHARASHIV (OSMANABAD), MAHARASHTRA - Times New Roman
   - NO textbox boundaries / boxes around the title. Pure clean text overlay.
2. Authentic North Arrow:
   - Circle + hollow triangle + 'N' below triangle.
   - Fully TRANSPARENT background (no white box/fill).
   - Placed in top-right corner inside the map panel.
3. Administrative Hierarchy on EVERY Map:
   - First: Block / Taluka Boundary (Bold Red line)
   - Second: Subdistricts / Village Boundaries (Clean subtle dash/boundary line)
   - Third: Village Headquarters / Settlements (Discreet dots and labels)
4. Specific Legend for whether Raster or Vector:
   - NO textbox boundaries / frame around legend (frameon=False).
   - Clear thematic handles (vector lines/points or raster classified patches).
5. Professional metric scale bar (alternating black/white) at bottom-left.
6. Calibrated DMS graticule tick marks on all 4 neatline borders.
"""

from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import pyproj
import rasterio
from rasterio.mask import mask
import scipy.ndimage

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
MAPS_DIR = MAP_DATA / "maps"

# Global font
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "Liberation Serif", "Times", "serif"]

# Core vector layers
AOI_BLOCKS = gpd.read_file(MAP_DATA / "aoi" / "aoi_blocks.gpkg").to_crs("EPSG:32643")
SUBBLOCKS = gpd.read_file(MAP_DATA / "aoi" / "subblocks_villages.gpkg").to_crs("EPSG:32643")
ROADS = gpd.read_file(MAP_DATA / "roads" / "roads_osm.gpkg").to_crs("EPSG:32643") if (MAP_DATA / "roads" / "roads_osm.gpkg").exists() else None
WELLS = gpd.read_file(MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg").to_crs("EPSG:32643") if (MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg").exists() else None
CONTOURS = gpd.read_file(MAP_DATA / "dem" / "contours_10m.gpkg").to_crs("EPSG:32643") if (MAP_DATA / "dem" / "contours_10m.gpkg").exists() else None
STREAMS = gpd.read_file(MAP_DATA / "streams" / "streams_complete_strahler.gpkg").to_crs("EPSG:32643") if (MAP_DATA / "streams" / "streams_complete_strahler.gpkg").exists() else None

TRANSFORMER_TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
TRANSFORMER_TO_WGS = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


def create_block_canvas(map_theme_title, block_name, orientation="landscape"):
    """
    Creates canvas with map axes filling the page inside neatlines.
    Tuljapur -> Landscape (20 x 15)
    Lohara -> Vertical / Portrait (15 x 20)
    """
    if orientation == "landscape":
        fig = plt.figure(figsize=(20.0, 15.0), dpi=300)
        # Margin: left, bottom, width, height
        map_rect = [0.05, 0.05, 0.90, 0.90]
        north_rect = [0.88, 0.86, 0.065, 0.08]
    else:
        fig = plt.figure(figsize=(15.0, 20.0), dpi=300)
        map_rect = [0.06, 0.05, 0.88, 0.90]
        north_rect = [0.86, 0.87, 0.075, 0.075]

    fig.patch.set_facecolor("#ffffff")

    # Outer border neatlines
    b_outer = mpatches.Rectangle((0.02, 0.02), 0.96, 0.96, fill=False, edgecolor="#000000", lw=2.2, transform=fig.transFigure, zorder=100)
    b_inner = mpatches.Rectangle((0.025, 0.025), 0.95, 0.95, fill=False, edgecolor="#000000", lw=0.9, transform=fig.transFigure, zorder=101)
    fig.artists.extend([b_outer, b_inner])

    ax_map = fig.add_axes(map_rect)
    ax_map.set_facecolor("#ffffff")
    for spine in ax_map.spines.values():
        spine.set_color("#000000")
        spine.set_linewidth(1.4)
    ax_map.tick_params(colors="#000000", labelsize=10, width=1.1, length=6, direction="out")

    # Transparent North Arrow inside top-right of map axes
    ax_north = fig.add_axes(north_rect)
    ax_north.patch.set_alpha(0.0)
    ax_north.set_aspect("equal")
    ax_north.axis("off")

    # Authentic user circle + triangle + N
    c = plt.Circle((0.5, 0.5), 0.44, fill=False, ec="#262626", lw=5.5)
    ax_north.add_patch(c)
    tri_pts = [[0.5, 0.83], [0.22, 0.45], [0.78, 0.45]]
    tri = plt.Polygon(tri_pts, closed=True, fill=False, ec="#262626", lw=5.2, joinstyle="miter")
    ax_north.add_patch(tri)
    ax_north.text(0.5, 0.23, "N", fontsize=24, fontweight="bold", fontfamily="sans-serif", ha="center", va="center", color="#262626")

    # Top Center Title INSIDE Mapping Panel (No box boundaries, pure clean serif text)
    ax_map.text(0.50, 0.975, map_theme_title.upper(), transform=ax_map.transAxes,
                fontsize=16, fontfamily="Times New Roman", ha="center", va="top", color="#0f172a", fontweight="normal", zorder=60)
    ax_map.text(0.50, 0.942, block_name.upper(), transform=ax_map.transAxes,
                fontsize=24, fontfamily="Times New Roman", ha="center", va="top", color="#000000", fontweight="bold", zorder=60)
    ax_map.text(0.50, 0.915, "DISTRICT DHARASHIV (OSMANABAD), MAHARASHTRA", transform=ax_map.transAxes,
                fontsize=10, fontfamily="Times New Roman", ha="center", va="top", color="#475569", style="italic", zorder=60)

    # Discreet bottom right attribution
    ax_map.text(0.99, 0.012, "Lead GIS Engineer & Cartographer | Survey of India Baseline", transform=ax_map.transAxes,
                fontsize=8, fontfamily="Times New Roman", ha="right", va="bottom", color="#64748b", style="italic", zorder=60)

    return fig, ax_map


def apply_block_dms_ticks(ax_map, minx, miny, maxx, maxy):
    """Calibrated DMS ticks at 5' intervals on all 4 borders."""
    lon1, lat1 = TRANSFORMER_TO_WGS.transform(minx, miny)
    lon2, lat2 = TRANSFORMER_TO_WGS.transform(maxx, maxy)

    lon_mins_start = int(np.floor(lon1 * 60 / 5) * 5)
    lon_mins_end = int(np.ceil(lon2 * 60 / 5) * 5)
    lat_mins_start = int(np.floor(lat1 * 60 / 5) * 5)
    lat_mins_end = int(np.ceil(lat2 * 60 / 5) * 5)

    xticks, xlabels = [], []
    yticks, ylabels = [], []

    for m in range(lon_mins_start, lon_mins_end + 1, 5):
        deg = m / 60.0
        d = int(deg)
        mins = int(round((deg - d) * 60))
        x, _ = TRANSFORMER_TO_UTM.transform(deg, (lat1 + lat2) / 2)
        if minx <= x <= maxx:
            xticks.append(x)
            xlabels.append(f"{d}\u00b0{mins:02d}'E")

    for m in range(lat_mins_start, lat_mins_end + 1, 5):
        deg = m / 60.0
        d = int(deg)
        mins = int(round((deg - d) * 60))
        _, y = TRANSFORMER_TO_UTM.transform((lon1 + lon2) / 2, deg)
        if miny <= y <= maxy:
            yticks.append(y)
            ylabels.append(f"{d}\u00b0{mins:02d}'N")

    ax_map.set_xticks(xticks)
    ax_map.set_xticklabels(xlabels, fontfamily="Times New Roman", fontsize=10, color="#000000")
    ax_map.set_yticks(yticks)
    ax_map.set_yticklabels(ylabels, fontfamily="Times New Roman", fontsize=10, color="#000000")
    ax_map.tick_params(top=True, right=True, labeltop=True, labelright=True, direction="out", length=6, width=1.2)


def draw_scale_bar(ax_map, length_km=10, x_frac=0.03, y_frac=0.035):
    """Draws metric scale bar at bottom left."""
    xlim = ax_map.get_xlim()
    ylim = ax_map.get_ylim()
    w = xlim[1] - xlim[0]
    h = ylim[1] - ylim[0]

    x0 = xlim[0] + x_frac * w
    y0 = ylim[0] + y_frac * h
    h_bar = 0.008 * h

    seg_m = (length_km * 1000.0) / 2.0
    ax_map.add_patch(mpatches.Rectangle((x0, y0), seg_m, h_bar, facecolor="#000000", edgecolor="#000000", lw=1.0, zorder=50))
    ax_map.add_patch(mpatches.Rectangle((x0 + seg_m, y0), seg_m, h_bar, facecolor="#ffffff", edgecolor="#000000", lw=1.0, zorder=50))

    ax_map.text(x0, y0 + h_bar * 1.5, "0", fontfamily="Times New Roman", fontsize=8.5, ha="center", va="bottom", zorder=51)
    ax_map.text(x0 + seg_m, y0 + h_bar * 1.5, f"{int(length_km/2)}", fontfamily="Times New Roman", fontsize=8.5, ha="center", va="bottom", zorder=51)
    ax_map.text(x0 + seg_m * 2, y0 + h_bar * 1.5, f"{int(length_km)}", fontfamily="Times New Roman", fontsize=8.5, ha="center", va="bottom", zorder=51)
    ax_map.text(x0 + seg_m * 2 * 1.25, y0, "Kilometers", fontfamily="Times New Roman", fontsize=9, ha="left", va="bottom", zorder=51)


def draw_legend(ax_map, handles, labels, x_frac=0.03, y_frac=0.08):
    """Draws legend without any textbox boundary."""
    leg = ax_map.legend(
        handles, labels,
        title="Legend",
        loc="lower left",
        bbox_to_anchor=(x_frac, y_frac),
        frameon=False,
        fontsize=10,
        title_fontproperties={"weight": "bold", "family": "Times New Roman", "size": 12},
        labelspacing=0.45
    )
    for text in leg.get_texts():
        text.set_fontfamily("Times New Roman")


def render_block_hillshade(ax_map, block_geom, alpha=0.30):
    """Renders 3D shaded relief clipped to block."""
    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    if not dem_path.exists():
        return
    with rasterio.open(dem_path) as src:
        out_arr, out_trans = mask(src, [block_geom], crop=True)
        dem = out_arr[0].astype("float32")
        dem[dem == src.nodata] = np.nan
        extent = [out_trans[2], out_trans[2] + out_trans[0] * dem.shape[1], out_trans[5] + out_trans[4] * dem.shape[0], out_trans[5]]
        ls = mcolors.LightSource(azdeg=315, altdeg=45)
        hs = ls.hillshade(dem, vert_exag=3.5)
        ax_map.imshow(hs, extent=extent, cmap="gray", vmin=0.0, vmax=1.0, alpha=alpha, zorder=1, interpolation="bilinear")


def render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False):
    """
    Renders the exact administrative hierarchy on EVERY map:
    1. Taluka / Block boundary (Red line)
    2. Subdistricts / Villages boundaries (subtle gray dashed lines)
    3. Village Headquarters (dots) and optional labels
    """
    # Subdistricts / Villages
    sub_v = SUBBLOCKS[SUBBLOCKS["BLOCK"] == block_name]
    sub_v.plot(ax=ax_map, facecolor="none", edgecolor="#94a3b8", linewidth=0.6, linestyle="--", alpha=0.75, zorder=3)

    if label_villages:
        # For Study Area and Admin Maps: label prominent village centers
        for _, r in sub_v.iterrows():
            cent = r.geometry.centroid
            v_name = str(r["VILLAGE"]).strip().title()
            ax_map.scatter(cent.x, cent.y, color="#dc2626", s=14, zorder=7)
            ax_map.text(cent.x, cent.y + 350, v_name, fontsize=6.5, fontfamily="Times New Roman",
                        ha="center", va="bottom", color="#1e293b", zorder=8)
    else:
        # Subtle village centroids for orientation on other thematic maps
        centroids = sub_v.geometry.centroid
        ax_map.scatter(centroids.x, centroids.y, color="#64748b", s=6, alpha=0.6, zorder=5)

    # 1. Primary Block Boundary (Bold Red)
    block_gdf.boundary.plot(ax=ax_map, color="#dc2626", linewidth=2.5, zorder=12)


def setup_map_view(ax_map, block_gdf):
    """Sets bounds and DMS ticks with 4% padding."""
    minx, miny, maxx, maxy = block_gdf.total_bounds
    padx = (maxx - minx) * 0.04
    pady = (maxy - miny) * 0.04
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_block_dms_ticks(ax_map, minx - padx, miny - pady, maxx + padx, maxy + pady)


# =====================================================================
# THEMATIC MAP RENDERERS (10 THEMES PER BLOCK)
# =====================================================================

def render_study_area(block_name, block_gdf, out_dir, orient):
    """1. Study Area Map."""
    fig, ax_map = create_block_canvas("STUDY AREA & REVENUE MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)
    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=True)

    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=6),
    ]
    labels = [f"{block_name} Taluka Boundary", "Village / Revenue Unit", "Village Center"]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"01_{block_name}_Study_Area_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_contour_map(block_name, block_gdf, out_dir, orient):
    """2. Contour Map."""
    fig, ax_map = create_block_canvas("CONTOUR (10m) TOPOGRAPHIC MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.35)
    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)

    if CONTOURS is not None:
        c_clipped = gpd.clip(CONTOURS, block_gdf)
        reg_c = c_clipped[c_clipped["is_index"] == 0]
        idx_c = c_clipped[c_clipped["is_index"] == 1]
        reg_c.plot(ax=ax_map, color="#854d0e", linewidth=0.45, alpha=0.75, zorder=6)
        idx_c.plot(ax=ax_map, color="#713f12", linewidth=0.95, alpha=0.95, zorder=7)

        labeled = set()
        for _, r in idx_c.iterrows():
            ev = int(r["elev_m"])
            if ev % 50 == 0 and ev not in labeled:
                labeled.add(ev)
                pt = r.geometry.interpolate(0.5, normalized=True)
                ax_map.text(pt.x, pt.y, f"{ev} m", fontsize=7.5, fontfamily="Times New Roman", color="#713f12",
                            ha="center", va="center", bbox=dict(boxstyle="square,pad=0.15", fc="#ffffff", ec="#a16207", lw=0.5, alpha=0.85), zorder=9)

    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        Line2D([0], [0], color="#713f12", lw=1.1),
        Line2D([0], [0], color="#854d0e", lw=0.5),
    ]
    labels = [f"{block_name} Boundary", "Village Boundary", "50m Index Contour", "10m Regular Contour"]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"02_{block_name}_Contour_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_lulc_map(block_name, block_gdf, out_dir, orient):
    """3. LULC Map."""
    fig, ax_map = create_block_canvas("LAND USE / LAND COVER (LULC) MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)

    lulc_tif = MAP_DATA / "lulc" / "lulc250k_1617_aoi_utm.tif"
    with rasterio.open(lulc_tif) as src:
        out_arr, out_trans = mask(src, [geom], crop=True, nodata=255)
        arr = out_arr[0]
        extent = [out_trans[2], out_trans[2] + out_trans[0] * arr.shape[1], out_trans[5] + out_trans[4] * arr.shape[0], out_trans[5]]
        rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.float32)
        color_lookup = {
            1: "#dc2626", 2: "#facc15", 3: "#f97316", 4: "#78350f", 5: "#84cc16",
            6: "#fef08a", 7: "#15803d", 9: "#166534", 10: "#4ade80", 14: "#d97706",
            16: "#0284c7", 17: "#0369a1"
        }
        for v, hex_c in color_lookup.items():
            rgba[arr == v] = mcolors.to_rgba(hex_c, alpha=0.78)
        ax_map.imshow(rgba, extent=extent, zorder=2)

    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)
    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        mpatches.Patch(facecolor="#facc15", edgecolor="none"),
        mpatches.Patch(facecolor="#84cc16", edgecolor="none"),
        mpatches.Patch(facecolor="#fef08a", edgecolor="none"),
        mpatches.Patch(facecolor="#d97706", edgecolor="none"),
        mpatches.Patch(facecolor="#0284c7", edgecolor="none"),
        mpatches.Patch(facecolor="#dc2626", edgecolor="none"),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "Kharif Cropland",
        "Double / Triple Crop", "Current Fallow", "Wasteland / Scrub", "Waterbody", "Settlement"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"03_{block_name}_LULC_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_soil_depth_map(block_name, block_gdf, out_dir, orient):
    """4. Soil Depth Map."""
    fig, ax_map = create_block_canvas("SOIL DEPTH CLASSIFICATION MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)

    soil_tif = MAP_DATA / "soil_depth" / "soildepth_aoi_utm.tif"
    with rasterio.open(soil_tif) as src:
        out_arr, out_trans = mask(src, [geom], crop=True, nodata=255)
        arr = out_arr[0]
        extent = [out_trans[2], out_trans[2] + out_trans[0] * arr.shape[1], out_trans[5] + out_trans[4] * arr.shape[0], out_trans[5]]
        rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.float32)
        rgba[arr == 1] = mcolors.to_rgba("#38bdf8", alpha=0.76)
        rgba[arr == 2] = mcolors.to_rgba("#f59e0b", alpha=0.76)
        rgba[arr == 4] = mcolors.to_rgba("#84cc16", alpha=0.76)
        ax_map.imshow(rgba, extent=extent, zorder=2)

    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)
    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        mpatches.Patch(facecolor="#84cc16", edgecolor="none"),
        mpatches.Patch(facecolor="#f59e0b", edgecolor="none"),
        mpatches.Patch(facecolor="#38bdf8", edgecolor="none"),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "Very Shallow (10-25 cm)",
        "Shallow (25-50 cm)", "Deep / Mod. Deep (>50 cm)"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"04_{block_name}_Soil_Depth_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_road_network_map(block_name, block_gdf, out_dir, orient):
    """5. Road Network Map."""
    fig, ax_map = create_block_canvas("CLASSIFIED ROAD NETWORK MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)
    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)

    if ROADS is not None:
        roads_clip = gpd.clip(ROADS, block_gdf)
        cls_colors = {"Trunk/Motorway": "#dc2626", "Primary": "#ea580c", "Secondary": "#d97706", "Tertiary": "#0284c7", "Residential/Unclassified": "#64748b", "Track/Path": "#94a3b8"}
        cls_widths = {"Trunk/Motorway": 2.6, "Primary": 2.2, "Secondary": 1.7, "Tertiary": 1.2, "Residential/Unclassified": 0.8, "Track/Path": 0.5}

        for r_cls in ["Track/Path", "Residential/Unclassified", "Tertiary", "Secondary", "Primary", "Trunk/Motorway"]:
            sub_r = roads_clip[roads_clip["road_class"] == r_cls]
            if len(sub_r) > 0:
                sub_r.plot(ax=ax_map, color=cls_colors.get(r_cls, "#64748b"), linewidth=cls_widths.get(r_cls, 0.8), zorder=6)

    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        Line2D([0], [0], color="#dc2626", lw=2.6),
        Line2D([0], [0], color="#ea580c", lw=2.2),
        Line2D([0], [0], color="#d97706", lw=1.7),
        Line2D([0], [0], color="#0284c7", lw=1.2),
        Line2D([0], [0], color="#64748b", lw=0.8),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "National Highway",
        "Major State Highway", "Major District Road", "Other District Road", "Rural / Village Road"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"05_{block_name}_Road_Network_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_rainfall_map(block_name, block_gdf, out_dir, orient):
    """6. Rainfall Map with Isohyets."""
    fig, ax_map = create_block_canvas("ANNUAL RAINFALL & ISOHYET MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)

    rain_path = MAP_DATA / "rainfall" / "rain_mean_mm_1991_2024.tif"
    with rasterio.open(rain_path) as src:
        out_arr, out_trans = mask(src, [geom.buffer(4000)], crop=True)
        arr = out_arr[0].astype("float32")
        arr_smooth = scipy.ndimage.zoom(arr, 25, order=3)
        arr_smooth = scipy.ndimage.gaussian_filter(arr_smooth, sigma=1.5)
        extent = [out_trans[2], out_trans[2] + out_trans[0] * arr.shape[1], out_trans[5] + out_trans[4] * arr.shape[0], out_trans[5]]

        vmin_r = np.nanmin(arr_smooth)
        vmax_r = np.nanmax(arr_smooth)
        ax_map.imshow(arr_smooth, extent=extent, cmap=plt.cm.YlGnBu, vmin=vmin_r, vmax=vmax_r, alpha=0.76, zorder=2)

        x_grid = np.linspace(extent[0], extent[1], arr_smooth.shape[1])
        y_grid = np.linspace(extent[3], extent[2], arr_smooth.shape[0])
        levels = np.arange(int(np.floor(vmin_r / 10) * 10), int(np.ceil(vmax_r / 10) * 10) + 10, 10)
        cs = ax_map.contour(x_grid, y_grid, arr_smooth, levels=levels, colors="#1e3a8a", linewidths=1.5, zorder=4)
        ax_map.clabel(cs, inline=True, fmt="%d mm", fontsize=9.5, colors="#0f172a")

    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)
    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        Line2D([0], [0], color="#1e3a8a", lw=1.5),
        mpatches.Patch(facecolor="#38bdf8", edgecolor="none"),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "Rainfall Isohyet (10mm Interval)",
        "34-Yr Mean Precipitation (CHIRPS)"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"06_{block_name}_Rainfall_Isohyet_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_lithology_map(block_name, block_gdf, out_dir, orient):
    """7. Lithology & Hydrogeology Map."""
    fig, ax_map = create_block_canvas("LITHOLOGY & HYDROGEOLOGY WELL MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.30)

    # Deccan Trap Basalt formation fill
    block_gdf.plot(ax=ax_map, facecolor="#fef08a", alpha=0.35, edgecolor="none", zorder=2)
    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)

    if WELLS is not None:
        wells_clip = gpd.clip(WELLS, block_gdf.buffer(5000))
        for _, w in wells_clip.iterrows():
            ax_map.scatter(w.geometry.x, w.geometry.y, color="#0284c7", s=60, edgecolor="#ffffff", lw=1.2, zorder=7)
            loc = str(w.get("Location", "Well")).title()
            depth = str(w.get("Depth_of_Drill__m_", "N/A"))
            ax_map.text(w.geometry.x + 300, w.geometry.y + 300, f"{loc}\n({depth}m)", fontsize=7, fontfamily="Times New Roman",
                        color="#0f172a", bbox=dict(boxstyle="round,pad=0.15", fc="#ffffff", ec="#cbd5e1", lw=0.5, alpha=0.88), zorder=8)

    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        mpatches.Patch(facecolor="#fef08a", edgecolor="#ca8a04", alpha=0.6),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#0284c7", markeredgecolor="#ffffff", markersize=8),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "Deccan Trap Basalt Formation",
        "CGWB Observation Well"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"07_{block_name}_Lithology_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_dem_map(block_name, block_gdf, out_dir, orient):
    """8. DEM Map with Hypsometric Tint."""
    fig, ax_map = create_block_canvas("DIGITAL ELEVATION MODEL (DEM) OF", block_name, orient)
    geom = block_gdf.geometry.union_all()

    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    with rasterio.open(dem_path) as src:
        out_arr, out_trans = mask(src, [geom], crop=True, nodata=np.nan)
        dem = out_arr[0].astype("float32")
        extent = [out_trans[2], out_trans[2] + out_trans[0] * dem.shape[1], out_trans[5] + out_trans[4] * dem.shape[0], out_trans[5]]

        ls = mcolors.LightSource(azdeg=315, altdeg=45)
        cmap_elev = plt.cm.terrain
        cmap_elev.set_bad(color="white", alpha=0.0)
        shaded = ls.shade(dem, cmap=cmap_elev, blend_mode="overlay", vert_exag=3.5, vmin=np.nanmin(dem), vmax=np.nanmax(dem))
        ax_map.imshow(shaded, extent=extent, zorder=2)

    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)
    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    cbar_sub = ax_map.inset_axes([0.03, 0.12, 0.28, 0.025])
    norm = mcolors.Normalize(vmin=np.nanmin(dem), vmax=np.nanmax(dem))
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap_elev), cax=cbar_sub, orientation="horizontal")
    cb.set_label("Elevation (Meters a.s.l.)", fontfamily="Times New Roman", fontsize=8.5, labelpad=2)
    cb.ax.tick_params(labelsize=8)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
    ]
    labels = [f"{block_name} Boundary", "Village Boundary"]
    draw_legend(ax_map, handles, labels, y_frac=0.17)

    out_file = out_dir / f"08_{block_name}_DEM_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_administrative_map(block_name, block_gdf, out_dir, orient):
    """9. Administrative & Revenue Map."""
    fig, ax_map = create_block_canvas("ADMINISTRATIVE & REVENUE MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.25)
    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=True)

    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markersize=6),
    ]
    labels = [f"{block_name} Taluka Boundary", "Village / Revenue Unit", "Village Headquarters"]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"09_{block_name}_Administrative_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def render_slope_map(block_name, block_gdf, out_dir, orient):
    """10. Slope Map (NBSS&LUP Slope Classification)."""
    fig, ax_map = create_block_canvas("SLOPE PERCENTAGE & RELIEF MAP OF", block_name, orient)
    geom = block_gdf.geometry.union_all()
    render_block_hillshade(ax_map, geom, alpha=0.20)

    slope_path = MAP_DATA / "slope" / "slope_deg_pct.tif"
    with rasterio.open(slope_path) as src:
        out_arr, out_trans = mask(src, [geom], crop=True, nodata=np.nan)
        slope_pct = out_arr[1].astype("float32")
        extent = [out_trans[2], out_trans[2] + out_trans[0] * slope_pct.shape[1], out_trans[5] + out_trans[4] * slope_pct.shape[0], out_trans[5]]

        rgba = np.zeros((slope_pct.shape[0], slope_pct.shape[1], 4), dtype=np.float32)
        rgba[(slope_pct >= 0) & (slope_pct < 1)] = mcolors.to_rgba("#dbeafe", alpha=0.76)
        rgba[(slope_pct >= 1) & (slope_pct < 3)] = mcolors.to_rgba("#bfdbfe", alpha=0.76)
        rgba[(slope_pct >= 3) & (slope_pct < 5)] = mcolors.to_rgba("#fef08a", alpha=0.76)
        rgba[(slope_pct >= 5) & (slope_pct < 10)] = mcolors.to_rgba("#f59e0b", alpha=0.76)
        rgba[slope_pct >= 10] = mcolors.to_rgba("#dc2626", alpha=0.76)

        ax_map.imshow(rgba, extent=extent, zorder=2)

    render_admin_hierarchy(ax_map, block_name, block_gdf, label_villages=False)
    setup_map_view(ax_map, block_gdf)
    draw_scale_bar(ax_map, length_km=10 if block_name == "Lohara" else 15)

    handles = [
        Line2D([0], [0], color="#dc2626", lw=2.5),
        Line2D([0], [0], color="#94a3b8", lw=0.8, linestyle="--"),
        mpatches.Patch(facecolor="#dbeafe", edgecolor="none"),
        mpatches.Patch(facecolor="#bfdbfe", edgecolor="none"),
        mpatches.Patch(facecolor="#fef08a", edgecolor="none"),
        mpatches.Patch(facecolor="#f59e0b", edgecolor="none"),
        mpatches.Patch(facecolor="#dc2626", edgecolor="none"),
    ]
    labels = [
        f"{block_name} Boundary", "Village Boundary", "0-1% Nearly Level",
        "1-3% Very Gently Sloping", "3-5% Gently Sloping", "5-10% Moderately Sloping", ">10% Strongly Sloping / Ridge"
    ]
    draw_legend(ax_map, handles, labels, y_frac=0.08)

    out_file = out_dir / f"10_{block_name}_Slope_Map.png"
    plt.savefig(out_file, dpi=300)
    plt.close()
    print("Saved:", out_file.name)


def main():
    print("=" * 70)
    print("PRODUCTION OF 20 DEDICATED BLOCK MAPS (10 TULJAPUR + 10 LOHARA)")
    print("Tuljapur: Landscape (20x15 in @ 300 DPI)")
    print("Lohara: Portrait / Vertical (15x20 in @ 300 DPI)")
    print("Features: Clean inside title, transparent north arrow, admin hierarchy, no-box legends")
    print("=" * 70)

    blocks = [
        ("Tuljapur", "landscape"),
        ("Lohara", "portrait")
    ]

    for block_name, orient in blocks:
        print(f"\n>>> Generating 10 Maps for {block_name} ({orient})...")
        out_dir = MAPS_DIR / block_name
        out_dir.mkdir(parents=True, exist_ok=True)
        block_gdf = AOI_BLOCKS[AOI_BLOCKS["NAME"] == block_name]

        render_study_area(block_name, block_gdf, out_dir, orient)
        render_contour_map(block_name, block_gdf, out_dir, orient)
        render_lulc_map(block_name, block_gdf, out_dir, orient)
        render_soil_depth_map(block_name, block_gdf, out_dir, orient)
        render_road_network_map(block_name, block_gdf, out_dir, orient)
        render_rainfall_map(block_name, block_gdf, out_dir, orient)
        render_lithology_map(block_name, block_gdf, out_dir, orient)
        render_dem_map(block_name, block_gdf, out_dir, orient)
        render_administrative_map(block_name, block_gdf, out_dir, orient)
        render_slope_map(block_name, block_gdf, out_dir, orient)

    print("\nSUCCESS: All 20 publication-quality block maps generated.")


if __name__ == "__main__":
    main()

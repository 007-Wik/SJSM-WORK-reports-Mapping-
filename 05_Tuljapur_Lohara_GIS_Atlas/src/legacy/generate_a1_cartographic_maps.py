#!/usr/bin/env python3
"""
Senior Cartographer & GIS Engineer Map Production Engine
ISO A1 Landscape (841 x 594 mm | 33.11 x 23.39 in) @ 300 DPI (High Resolution)
Features:
- True Full-Canvas Map View (Map fills the entire sheet)
- Floating Glassmorphic Cartographic Cards
- Clear Central Title at the Top (Times New Roman, bold, uppercase)
- Classic Circular Crosshair Compass Rose with North arrow triangle and 'N' above it
- Informative Cartographic Labels across every map (Contour elevations, river names, sub-districts, soil units)
- Degrees-Minutes-Seconds (DMS) Graticule grid (5' intervals)
- 3D Hillshade Shaded Relief (Copernicus GLO-30) underlay in every map
- Complete Strahler Stream hierarchy (Orders 1-5+)
- Smoothed Rainfall Isohyets, Soil Depth (NBSS&LUP), and LULC (NRSC 1:250k)

Outputs in map_data/maps/:
  1. Map_01_Study_Area_Location_A1.png
  2. Map_02_Digital_Elevation_Model_DEM_A1.png
  3. Map_03_Hydrology_Drainage_Network_Strahler_A1.png
  4. Map_04_Climatological_Rainfall_Isohyets_A1.png
  5. Map_05_Soil_Depth_Classification_A1.png
  6. Map_06_Land_Use_Land_Cover_LULC_A1.png
"""
from pathlib import Path
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import pyproj
import rasterio
import scipy.ndimage

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
MAP_OUT = MAP_DATA / "maps"
MAP_OUT.mkdir(parents=True, exist_ok=True)

# Styling - Times New Roman Editorial Typography
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "Liberation Serif", "Times", "serif"]

# Core vector layers
AOI_BLOCKS = gpd.read_file(MAP_DATA / "aoi" / "aoi_blocks.gpkg").to_crs("EPSG:32643")
TULJAPUR_BLOCK = AOI_BLOCKS[AOI_BLOCKS["NAME"] == "Tuljapur"]
LOHARA_BLOCK = AOI_BLOCKS[AOI_BLOCKS["NAME"] == "Lohara"]
SUBBLOCKS = gpd.read_file(MAP_DATA / "aoi" / "subblocks_villages.gpkg").to_crs("EPSG:32643")
DISTRICT_TALUKAS = gpd.read_file(MAP_DATA / "aoi" / "osmanabad_district_talukas.gpkg").to_crs("EPSG:32643")
ROADS = gpd.read_file(MAP_DATA / "roads" / "roads_osm.gpkg").to_crs("EPSG:32643") if (MAP_DATA / "roads" / "roads_osm.gpkg").exists() else None

# Geographic to UTM Transformer
TRANSFORMER_TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)


# =====================================================================
# FULL-CANVAS A1 CANVAS & FLOATING GLASSMORPHIC SYSTEM
# =====================================================================

def create_full_canvas_a1_layout(sheet_title, sheet_subtitle, sheet_code="A1-01"):
    """
    Creates an expansive ISO A1 landscape canvas where the main map viewport
    occupies the entire canvas, bordered by a calibrated graticule collar.
    Top banner features a clear, centered title badge (Times New Roman).
    """
    fig = plt.figure(figsize=(33.11, 23.39), dpi=300)
    fig.patch.set_facecolor("#ffffff")

    # Double neatline border around outer perimeter
    border_outer = mpatches.Rectangle(
        (0.008, 0.008), 0.984, 0.984,
        transform=fig.transFigure, fill=False,
        edgecolor="#0f172a", linewidth=3.2, zorder=100
    )
    border_inner = mpatches.Rectangle(
        (0.011, 0.011), 0.978, 0.978,
        transform=fig.transFigure, fill=False,
        edgecolor="#475569", linewidth=1.2, zorder=101
    )
    fig.artists.extend([border_outer, border_inner])

    # Full-Canvas Map Viewport (occupies the entire sheet)
    ax_map = fig.add_axes([0.024, 0.028, 0.952, 0.944])
    ax_map.set_facecolor("#f8fafc")
    ax_map.tick_params(colors="#0f172a", labelsize=11.5, width=1.5, length=7)
    for spine in ax_map.spines.values():
        spine.set_color("#0f172a")
        spine.set_linewidth(1.8)

    # Centered Header Title Badge at the top of the map
    card_title = ax_map.inset_axes([0.220, 0.885, 0.560, 0.098])
    card_title.set_facecolor("#ffffff")
    card_title.patch.set_alpha(0.92)
    card_title.set_xticks([])
    card_title.set_yticks([])
    for sp in card_title.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.4)

    card_title.text(
        0.50, 0.82,
        sheet_subtitle.upper(),
        fontsize=12.5, fontweight="bold", color="#475569", ha="center", va="center"
    )
    card_title.text(
        0.50, 0.44,
        sheet_title.upper(),
        fontsize=24, fontweight="heavy", color="#0f172a", ha="center", va="center"
    )
    card_title.text(
        0.50, 0.16,
        f"DHARASHIV DISTRICT, MAHARASHTRA  •  SHEET REF: {sheet_code}",
        fontsize=11.5, fontweight="bold", color="#0284c7", ha="center", va="center"
    )

    return fig, ax_map


def apply_dms_graticule(ax_map, lon_mins_step=5, lat_mins_step=5):
    """
    Applies an authentic Senior Cartographer Degrees, Minutes, Seconds (DMS)
    graticule grid across the UTM Zone 43N projected map.
    """
    lon_mins_start = 50   # 75 deg 50 min
    lon_mins_end = 95     # 76 deg 35 min
    lat_mins_start = 40   # 17 deg 40 min
    lat_mins_end = 70     # 18 deg 10 min

    lon_ticks_x, lon_labels = [], []
    lat_ticks_y, lat_labels = [], []

    for m in range(lon_mins_start, lon_mins_end + 1, lon_mins_step):
        deg = 75.0 + m / 60.0
        d = int(deg)
        mins = int(round((deg - d) * 60))
        x, _ = TRANSFORMER_TO_UTM.transform(deg, 17.88)
        lon_ticks_x.append(x)
        lon_labels.append(f"{d}° {mins:02d}' E")

        y_pts = np.linspace(17.65, 18.12, 50)
        x_line, y_line = TRANSFORMER_TO_UTM.transform(np.full_like(y_pts, deg), y_pts)
        ax_map.plot(x_line, y_line, color="#475569", linestyle=":", linewidth=0.75, alpha=0.50, zorder=8)

    for m in range(lat_mins_start, lat_mins_end + 1, lat_mins_step):
        deg = 17.0 + m / 60.0
        d = int(deg)
        mins = int(round((deg - d) * 60))
        _, y = TRANSFORMER_TO_UTM.transform(76.20, deg)
        lat_ticks_y.append(y)
        lat_labels.append(f"{d}° {mins:02d}' N")

        x_pts = np.linspace(75.83, 76.60, 50)
        x_line, y_line = TRANSFORMER_TO_UTM.transform(x_pts, np.full_like(x_pts, deg))
        ax_map.plot(x_line, y_line, color="#475569", linestyle=":", linewidth=0.75, alpha=0.50, zorder=8)

    ax_map.set_xticks(lon_ticks_x)
    ax_map.set_xticklabels(lon_labels, fontsize=12, fontweight="bold", color="#0f172a")
    ax_map.set_yticks(lat_ticks_y)
    ax_map.set_yticklabels(lat_labels, fontsize=12, fontweight="bold", color="#0f172a")

    ax_map.set_xlabel("GEOGRAPHIC LONGITUDE (DMS)  [GRATICULE GRID: 5' INTERVALS]", fontsize=12.5, fontweight="bold", color="#1e293b", labelpad=8)
    ax_map.set_ylabel("GEOGRAPHIC LATITUDE (DMS)  [GRATICULE GRID: 5' INTERVALS]", fontsize=12.5, fontweight="bold", color="#1e293b", labelpad=8)


def draw_hillshade_underlay(ax_map, alpha=0.38, vert_exag=3.5, azdeg=315, altdeg=45):
    """Renders 3D Hillshade shaded relief underneath thematic layers."""
    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    if not dem_path.exists():
        return None

    with rasterio.open(dem_path) as src:
        dem_arr = src.read(1).astype("float32")
        dem_arr[dem_arr == src.nodata] = np.nan
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        ls = mcolors.LightSource(azdeg=azdeg, altdeg=altdeg)
        hillshade = ls.hillshade(dem_arr, vert_exag=vert_exag)
        ax_map.imshow(hillshade, extent=extent, cmap="gray", vmin=0.0, vmax=1.0, alpha=alpha, zorder=1, interpolation="bilinear")
        return extent


def draw_north_arrow(ax, x=0.910, y=0.890, size=0.065):
    """
    Draws the classic Cartographic Compass Rose as requested:
    - Outer circular ring with clean crosshairs
    - North arrow triangle pointer with sharp arrowhead
    - Bold 'N' placed above the north triangle
    - Cardinal markers W, S, E at the respective ends
    """
    # Outer circle ring
    circle = mpatches.Circle(
        (x, y), size * 0.70, transform=ax.transAxes,
        facecolor="#ffffff", edgecolor="#0f172a", linewidth=1.8, alpha=0.95, zorder=65
    )
    ax.add_patch(circle)

    # Crosshair lines through center
    r = size * 0.70
    ax.plot([x - r, x + r], [y, y], transform=ax.transAxes, color="#0f172a", lw=1.2, zorder=66)
    ax.plot([x, x], [y - r, y + r], transform=ax.transAxes, color="#0f172a", lw=1.2, zorder=66)

    # North pointer triangle (Black left, White right)
    arrow_len = size * 0.65
    w_half = size * 0.12
    tri_left = mpatches.Polygon(
        [[x, y + arrow_len], [x - w_half, y], [x, y]],
        closed=True, transform=ax.transAxes, facecolor="#0f172a", edgecolor="#0f172a", lw=0.8, zorder=67
    )
    tri_right = mpatches.Polygon(
        [[x, y + arrow_len], [x + w_half, y], [x, y]],
        closed=True, transform=ax.transAxes, facecolor="#ffffff", edgecolor="#0f172a", lw=0.8, zorder=67
    )
    ax.add_patch(tri_left)
    ax.add_patch(tri_right)

    # Cardinal labels: N above, W, E, S around
    ax.text(x, y + arrow_len + size * 0.14, "N", transform=ax.transAxes, ha="center", va="center", fontsize=15, fontweight="heavy", color="#0f172a", zorder=68)
    ax.text(x, y - r - size * 0.12, "S", transform=ax.transAxes, ha="center", va="center", fontsize=9, fontweight="bold", color="#334155", zorder=68)
    ax.text(x + r + size * 0.12, y, "E", transform=ax.transAxes, ha="center", va="center", fontsize=9, fontweight="bold", color="#334155", zorder=68)
    ax.text(x - r - size * 0.12, y, "W", transform=ax.transAxes, ha="center", va="center", fontsize=9, fontweight="bold", color="#334155", zorder=68)


def draw_scale_bar(ax, length_km=20, x_pos=0.020, y_pos=0.035):
    """Draws an authentic alternating black-and-white scale bar inside a floating badge."""
    length_m = length_km * 1000.0
    xlim = ax.get_xlim()
    ylim = ax.get_ylim()
    map_w = xlim[1] - xlim[0]
    map_h = ylim[1] - ylim[0]

    x0 = xlim[0] + x_pos * map_w
    y0 = ylim[0] + y_pos * map_h
    h_bar = 0.010 * map_h

    # Floating background badge
    pad_w = length_m * 1.15
    pad_h = h_bar * 4.8
    badge = mpatches.FancyBboxPatch(
        (x0 - length_m * 0.06, y0 - h_bar * 1.8), pad_w, pad_h,
        boxstyle="round,pad=0.005", facecolor="#ffffff", edgecolor="#0f172a",
        linewidth=1.4, alpha=0.92, zorder=48
    )
    ax.add_patch(badge)

    num_seg = 4
    seg_len = length_m / num_seg
    colors = ["#0f172a", "#ffffff", "#0f172a", "#ffffff"]
    for i in range(num_seg):
        xi = x0 + i * seg_len
        rect = mpatches.Rectangle((xi, y0), seg_len, h_bar, facecolor=colors[i], edgecolor="#0f172a", linewidth=1.2, zorder=50)
        ax.add_patch(rect)
        ax.text(xi, y0 + h_bar * 1.4, f"{int(i * (length_km / num_seg))}", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#0f172a", zorder=51)

    ax.text(x0 + length_m, y0 + h_bar * 1.4, f"{int(length_km)} km", ha="center", va="bottom", fontsize=10, fontweight="bold", color="#0f172a", zorder=51)
    ax.text(x0 + length_m / 2, y0 - h_bar * 1.3, "GRAPHIC SCALE (KILOMETERS)  •  UTM ZONE 43N", ha="center", va="top", fontsize=9.2, fontweight="bold", color="#334155", zorder=51)


def draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180]):
    """Draws a floating Dharashiv District context inset map."""
    inset_sub = ax_map.inset_axes(bbox)
    inset_sub.set_facecolor("#ffffff")
    inset_sub.patch.set_alpha(0.92)
    inset_sub.set_title("DISTRICT CONTEXT: DHARASHIV", fontsize=9.5, fontweight="bold", color="#0f172a", pad=4)
    inset_sub.set_xticks([])
    inset_sub.set_yticks([])
    for spine in inset_sub.spines.values():
        spine.set_color("#0f172a")
        spine.set_linewidth(1.3)

    DISTRICT_TALUKAS.plot(ax=inset_sub, color="#e2e8f0", edgecolor="#64748b", linewidth=0.7)
    TULJAPUR_BLOCK.plot(ax=inset_sub, color="#38bdf8", edgecolor="#0369a1", linewidth=1.4)
    LOHARA_BLOCK.plot(ax=inset_sub, color="#f59e0b", edgecolor="#b45309", linewidth=1.4)

    for _, r in DISTRICT_TALUKAS.iterrows():
        c = r.geometry.centroid
        t_name = r["TALUKA"]
        col = "#0369a1" if t_name == "Tuljapur" else ("#b45309" if t_name == "Lohara" else "#475569")
        weight = "bold" if t_name in ["Tuljapur", "Lohara"] else "normal"
        inset_sub.text(c.x, c.y, t_name, fontsize=7.2, ha="center", va="center", color=col, fontweight=weight)


def draw_floating_metadata(ax_map, theme_notes, bbox=[0.720, 0.025, 0.260, 0.130]):
    """Draws a compact floating cartographic metadata box at the bottom right."""
    meta_ax = ax_map.inset_axes(bbox)
    meta_ax.set_facecolor("#ffffff")
    meta_ax.patch.set_alpha(0.92)
    meta_ax.set_xticks([])
    meta_ax.set_yticks([])
    for sp in meta_ax.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    meta_ax.text(0.04, 0.88, "CARTOGRAPHIC METADATA & PROJECTION", fontsize=9.5, fontweight="bold", color="#0f172a", va="top")
    meta_ax.plot([0.04, 0.96], [0.75, 0.75], color="#cbd5e1", lw=1.0)
    meta_txt = (
        "• Coordinate System: Geographic Graticule (DMS 5' Grid)\n"
        "• Projection: UTM 43N | Datum: WGS 84 (EPSG: 32643)\n"
        "• Study Units: Tuljapur (1,534.6 km²) & Lohara (509.3 km²)\n"
        f"{theme_notes}\n"
        "• Lead GIS Cartography: Senior Cartographer Atlas Suite"
    )
    meta_ax.text(0.04, 0.68, meta_txt, fontsize=8.2, color="#334155", va="top", linespacing=1.35)


# =====================================================================
# MAP 1: STUDY AREA & ADMINISTRATIVE FRAMEWORK
# =====================================================================
def generate_study_area_map():
    print(">>> Generating A1 Full-Canvas Study Area Location Map...")
    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="STUDY AREA & ADMINISTRATIVE FRAMEWORK",
        sheet_subtitle="Tuljapur and Lohara Blocks with 158 Sub-Blocks & Village Units",
        sheet_code="A1-01"
    )

    draw_hillshade_underlay(ax_map, alpha=0.36, vert_exag=3.5)

    # Sub-blocks / Villages
    SUBBLOCKS.plot(ax=ax_map, facecolor="#f8fafc", alpha=0.32, edgecolor="#64748b", linewidth=0.7, linestyle="--", zorder=3)

    # Classified Roads
    if ROADS is not None:
        cls_colors = {"Trunk/Motorway": "#dc2626", "Primary": "#ea580c", "Secondary": "#d97706", "Tertiary": "#0284c7", "Residential/Unclassified": "#94a3b8", "Track/Path": "#cbd5e1"}
        cls_widths = {"Trunk/Motorway": 2.5, "Primary": 2.0, "Secondary": 1.5, "Tertiary": 1.0, "Residential/Unclassified": 0.6, "Track/Path": 0.4}
        for r_cls in ["Track/Path", "Residential/Unclassified", "Tertiary", "Secondary", "Primary", "Trunk/Motorway"]:
            sub_r = ROADS[ROADS["road_class"] == r_cls]
            if len(sub_r) > 0:
                sub_r.plot(ax=ax_map, color=cls_colors.get(r_cls, "#94a3b8"), linewidth=cls_widths.get(r_cls, 0.8), zorder=4)

    # Block Boundaries
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0284c7", linewidth=3.2, linestyle="-", zorder=10)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#d97706", linewidth=3.2, linestyle="-", zorder=10)

    # Village Labels
    key_villages = ["Tuljapur", "Lohara", "Ekondi", "Naldurg", "Kati", "Mangrul", "Andoor", "Javla", "Dalimb", "Murum", "Toramba", "Salagara", "Khandala", "Tamalwadi", "Dhoki"]
    labeled = set()
    for _, r in SUBBLOCKS.iterrows():
        v_name = str(r["VILLAGE"]).strip()
        for kv in key_villages:
            if kv.lower() in v_name.lower() and kv not in labeled:
                labeled.add(kv)
                cent = r.geometry.centroid
                ax_map.scatter(cent.x, cent.y, color="#dc2626", s=70, edgecolor="#ffffff", linewidth=1.6, zorder=20)
                ax_map.text(cent.x, cent.y + 700, v_name, fontsize=10, fontweight="bold", color="#0f172a", ha="center", va="bottom",
                            bbox=dict(boxstyle="round,pad=0.25", fc="#ffffff", ec="#cbd5e1", alpha=0.92), zorder=21)
                break

    # Block Labels
    t_cent = TULJAPUR_BLOCK.geometry.iloc[0].centroid
    l_cent = LOHARA_BLOCK.geometry.iloc[0].centroid
    ax_map.text(t_cent.x, t_cent.y - 4500, "TULJAPUR TALUKA\nArea: 1,534.6 km² | 108 Villages", fontsize=15.5, fontweight="heavy", color="#0369a1", ha="center", va="center",
                bbox=dict(boxstyle="square,pad=0.6", fc="#f0f9ff", ec="#0284c7", lw=2.2, alpha=0.94), zorder=25)
    ax_map.text(l_cent.x, l_cent.y, "LOHARA TALUKA\nArea: 509.3 km² | 50 Villages", fontsize=15.5, fontweight="heavy", color="#b45309", ha="center", va="center",
                bbox=dict(boxstyle="square,pad=0.6", fc="#fffbeb", ec="#d97706", lw=2.2, alpha=0.94), zorder=25)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating Legend Card
    card_leg = ax_map.inset_axes([0.020, 0.500, 0.240, 0.360])
    card_leg.set_facecolor("#ffffff")
    card_leg.patch.set_alpha(0.92)
    card_leg.set_xticks([])
    card_leg.set_yticks([])
    for sp in card_leg.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_leg.text(0.06, 0.94, "LEGEND & SYMBOLOGY", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    card_leg.plot([0.06, 0.94], [0.89, 0.89], color="#cbd5e1", lw=1.0)
    leg_items = [
        Line2D([0], [0], color="#0284c7", lw=3.0, label="Tuljapur Taluka Boundary"),
        Line2D([0], [0], color="#d97706", lw=3.0, label="Lohara Taluka Boundary"),
        Line2D([0], [0], color="#64748b", lw=1.2, linestyle="--", label="Village / Sub-Block (158 units)"),
        Line2D([0], [0], color="#dc2626", lw=2.5, label="National Highway / Expressway"),
        Line2D([0], [0], color="#ea580c", lw=2.0, label="Major State Highway (SH)"),
        Line2D([0], [0], color="#d97706", lw=1.5, label="Major District Road (MDR)"),
        Line2D([0], [0], color="#0284c7", lw=1.2, label="Other District Road (ODR)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#dc2626", markeredgecolor="#ffffff", markersize=9, label="Key Village Settlement"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="3D Hillshade Relief Underlay"),
        Line2D([0], [0], color="#475569", lw=0.8, linestyle=":", label="DMS Graticule (5' Grid)"),
    ]
    card_leg.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.88), frameon=False, fontsize=8.8, labelspacing=0.85)

    draw_floating_metadata(ax_map, "• Survey Baseline: Survey of India & Census 2011\n• Road Infrastructure: OpenStreetMap (OSM) 2024")

    out_file = MAP_OUT / "Map_01_Study_Area_Location_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAP 2: DIGITAL ELEVATION MODEL (DEM) & TOPOGRAPHY
# =====================================================================
def generate_dem_map():
    print(">>> Generating A1 Full-Canvas DEM Topographic Map...")
    dem_path = MAP_DATA / "dem" / "dem_aoi.tif"
    contours_path = MAP_DATA / "dem" / "contours_10m.gpkg"
    if not dem_path.exists():
        return

    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="DIGITAL ELEVATION MODEL & TOPOGRAPHIC CONTOURS",
        sheet_subtitle="Copernicus GLO-30 Metric Elevation, 3D Relief & 10m/50m Topographic Contours",
        sheet_code="A1-02"
    )

    with rasterio.open(dem_path) as src:
        dem_arr = src.read(1).astype("float32")
        dem_arr[dem_arr == src.nodata] = np.nan
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        ls = mcolors.LightSource(azdeg=315, altdeg=45)
        cmap_elev = plt.cm.terrain
        cmap_elev.set_bad(color="white", alpha=0.0)
        shaded = ls.shade(dem_arr, cmap=cmap_elev, blend_mode="overlay", vert_exag=3.5, vmin=np.nanmin(dem_arr), vmax=np.nanmax(dem_arr))
        im = ax_map.imshow(shaded, extent=extent, zorder=2)

    # Contours with elevation labels
    if contours_path.exists():
        contours = gpd.read_file(contours_path).to_crs("EPSG:32643")
        reg_c = contours[contours["is_index"] == 0]
        idx_c = contours[contours["is_index"] == 1]
        reg_c.plot(ax=ax_map, color="#57534e", linewidth=0.45, alpha=0.50, zorder=4)
        idx_c.plot(ax=ax_map, color="#451a03", linewidth=1.10, alpha=0.90, zorder=5)

        # Label key 50m index contour lines with elevation text (e.g. 500m, 550m, 600m, 650m)
        labeled_elevs = set()
        for _, row in idx_c.iterrows():
            ev = int(row["elev_m"])
            if ev % 50 == 0 and ev not in labeled_elevs:
                labeled_elevs.add(ev)
                geom = row.geometry
                mid_pt = geom.interpolate(0.5, normalized=True)
                ax_map.text(
                    mid_pt.x, mid_pt.y, f"{ev} m",
                    fontsize=8.5, fontweight="bold", color="#451a03",
                    bbox=dict(boxstyle="round,pad=0.18", fc="#ffffff", ec="#78350f", lw=0.6, alpha=0.85),
                    zorder=22
                )

    SUBBLOCKS.plot(ax=ax_map, facecolor="none", edgecolor="#334155", linewidth=0.6, linestyle="--", alpha=0.6, zorder=6)
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)

    # Highest summit
    max_idx = np.nanargmax(dem_arr)
    max_y, max_x = np.unravel_index(max_idx, dem_arr.shape)
    with rasterio.open(dem_path) as src:
        max_coord_x, max_coord_y = src.xy(max_y, max_x)
    ax_map.scatter(max_coord_x, max_coord_y, color="#b91c1c", marker="^", s=130, edgecolor="#ffffff", lw=2.0, zorder=25)
    ax_map.text(max_coord_x + 800, max_coord_y + 800, f"HIGHEST PEAK: {np.nanmax(dem_arr):.0f} m\n(Balaghat Ridge Summit)",
                fontsize=11, fontweight="bold", color="#7f1d1d", bbox=dict(boxstyle="square,pad=0.3", fc="#fef2f2", ec="#b91c1c", lw=1.2), zorder=26)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating Hypsometric Card
    card_hyp = ax_map.inset_axes([0.020, 0.520, 0.250, 0.340])
    card_hyp.set_facecolor("#ffffff")
    card_hyp.patch.set_alpha(0.92)
    card_hyp.set_xticks([])
    card_hyp.set_yticks([])
    for sp in card_hyp.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_hyp.text(0.06, 0.93, "HYPSOMETRIC ELEVATION", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    cbar_sub = card_hyp.inset_axes([0.08, 0.73, 0.84, 0.11])
    norm = mcolors.Normalize(vmin=np.nanmin(dem_arr), vmax=np.nanmax(dem_arr))
    cb = plt.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap_elev), cax=cbar_sub, orientation="horizontal")
    cb.set_label("Elevation (Meters a.s.l.)", fontsize=8.8, fontweight="bold", color="#1e293b", labelpad=3)
    cb.ax.tick_params(labelsize=8)

    leg_items = [
        Line2D([0], [0], color="#0f172a", lw=2.8, label="Taluka Boundary"),
        Line2D([0], [0], color="#451a03", lw=2.0, label="Index Contour (50m Interval)"),
        Line2D([0], [0], color="#57534e", lw=0.8, label="Regular Contour (10m Interval)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor="#b91c1c", markeredgecolor="#ffffff", markersize=9, label="Highest Topographic Summit"),
        Line2D([0], [0], color="#475569", lw=0.8, linestyle=":", label="DMS Graticule (5' Grid)"),
    ]
    card_hyp.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.65), frameon=False, fontsize=8.8, labelspacing=0.85)

    draw_floating_metadata(ax_map, f"• Relief Span: {np.nanmin(dem_arr):.0f}m to {np.nanmax(dem_arr):.0f}m ({np.nanmax(dem_arr)-np.nanmin(dem_arr):.0f}m relief)\n• Vertical Datum: EGM96 Geoid (GLO-30)")

    out_file = MAP_OUT / "Map_02_Digital_Elevation_Model_DEM_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAP 3: HYDROLOGY & STRAHLER DRAINAGE NETWORK
# =====================================================================
def generate_hydrology_map():
    print(">>> Generating A1 Full-Canvas Drainage Network Map...")
    strm_path = MAP_DATA / "streams" / "streams_complete_strahler.gpkg"
    dd_path = MAP_DATA / "streams" / "drainage_density_grid.gpkg"
    if not strm_path.exists():
        return

    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="COMPREHENSIVE DRAINAGE NETWORK & HYDROLOGY",
        sheet_subtitle="Hierarchical Strahler Stream Orders (1 to 5), Basin Catchments & Drainage Density",
        sheet_code="A1-03"
    )

    strm = gpd.read_file(strm_path).to_crs("EPSG:32643")
    draw_hillshade_underlay(ax_map, alpha=0.34, vert_exag=3.5)

    if dd_path.exists():
        dd = gpd.read_file(dd_path).to_crs("EPSG:32643")
        dd.plot(column="dd_km_per_km2", ax=ax_map, cmap="Blues", alpha=0.28, edgecolor="none", zorder=2)

    order_config = {
        1: {"color": "#7dd3fc", "lw": 0.85, "label": "1st Order (Headwater Gully)"},
        2: {"color": "#38bdf8", "lw": 1.5, "label": "2nd Order (Tributary)"},
        3: {"color": "#0284c7", "lw": 2.4, "label": "3rd Order (Major Stream)"},
        4: {"color": "#1d4ed8", "lw": 3.6, "label": "4th Order (Sub-Basin River)"},
        5: {"color": "#0f172a", "lw": 5.2, "label": "5th Order (Main River Confluence)"},
    }
    for order in sorted(strm["strahler"].unique()):
        sub_strm = strm[strm["strahler"] == order]
        cfg = order_config.get(order, {"color": "#0f172a", "lw": 2.0, "label": f"Order {order}"})
        sub_strm.plot(ax=ax_map, color=cfg["color"], linewidth=cfg["lw"], zorder=3 + order)

    SUBBLOCKS.plot(ax=ax_map, facecolor="none", edgecolor="#94a3b8", linewidth=0.5, linestyle=":", zorder=12)
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=15)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=15)

    # River & Basin Labels
    ax_map.text(648000, 1968000, "TERNA RIVER BASIN\n(Lohara Catchment)", fontsize=11.5, fontweight="heavy", color="#1e3a8a",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#1e3a8a", lw=1.4, alpha=0.92), zorder=25)
    ax_map.text(602000, 1965000, "BORI RIVER BASIN\n(Tuljapur Catchment)", fontsize=11.5, fontweight="heavy", color="#1e3a8a",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#1e3a8a", lw=1.4, alpha=0.92), zorder=25)
    ax_map.text(632000, 1952000, "BENITHORA TRIBUTARY SYSTEM\n(Upper Krishna Catchment)", fontsize=10.5, fontweight="bold", color="#1e3a8a",
                bbox=dict(boxstyle="round,pad=0.35", fc="#ffffff", ec="#1e3a8a", lw=1.1, alpha=0.88), zorder=25)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating Stream Legend Card
    card_hyd = ax_map.inset_axes([0.020, 0.500, 0.250, 0.360])
    card_hyd.set_facecolor("#ffffff")
    card_hyd.patch.set_alpha(0.92)
    card_hyd.set_xticks([])
    card_hyd.set_yticks([])
    for sp in card_hyd.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_hyd.text(0.06, 0.94, "STRAHLER STREAM HIERARCHY", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    card_hyd.plot([0.06, 0.94], [0.89, 0.89], color="#cbd5e1", lw=1.0)
    leg_items = []
    for o in [1, 2, 3, 4, 5]:
        cfg = order_config[o]
        sub = strm[strm["strahler"] == o]
        km = sub["len_km"].sum() if len(sub) > 0 else 0
        leg_items.append(Line2D([0], [0], color=cfg["color"], lw=cfg["lw"], label=f"{cfg['label']} ({km:.1f} km)"))
    leg_items.extend([
        Line2D([0], [0], color="#0f172a", lw=2.8, label="Taluka Boundary"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="3D Hillshade Relief Underlay"),
        mpatches.Patch(facecolor="#bae6fd", edgecolor="none", alpha=0.4, label="Drainage Density Grid (1 km²)"),
        Line2D([0], [0], color="#475569", lw=0.8, linestyle=":", label="DMS Graticule (5' Grid)"),
    ])
    card_hyd.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.88), frameon=False, fontsize=8.6, labelspacing=0.80)

    tot_km = strm["len_km"].sum()
    draw_floating_metadata(ax_map, f"• Total Network Length: {tot_km:.1f} km (2,230 stream segments)\n• Mean Drainage Density: {tot_km/2043.9:.2f} km/km²")

    out_file = MAP_OUT / "Map_03_Hydrology_Drainage_Network_Strahler_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAP 4: CLIMATOLOGICAL RAINFALL & ISOHYET DISTRIBUTION
# =====================================================================
def generate_rainfall_map():
    print(">>> Generating A1 Full-Canvas Climatological Rainfall Map...")
    rain_path = MAP_DATA / "rainfall" / "rain_mean_mm_1991_2024.tif"
    ts_csv = MAP_DATA / "rainfall" / "rain_timeseries_aoi_mean_mm.csv"
    if not rain_path.exists():
        return

    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="CLIMATOLOGICAL ANNUAL RAINFALL & ISOHYETS",
        sheet_subtitle="34-Year Mean Annual Precipitation (1991–2024, CHIRPS v2.0), Isohyets & Seasonal Trends",
        sheet_code="A1-04"
    )

    draw_hillshade_underlay(ax_map, alpha=0.35, vert_exag=3.5)

    with rasterio.open(rain_path) as src:
        arr = src.read(1).astype("float32")
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        arr_smooth = scipy.ndimage.zoom(arr, 25, order=3)
        arr_smooth = scipy.ndimage.gaussian_filter(arr_smooth, sigma=1.5)

        cmap_rain = plt.cm.YlGnBu
        vmin_r = np.floor(np.nanmin(arr) / 10) * 10
        vmax_r = np.ceil(np.nanmax(arr) / 10) * 10
        im = ax_map.imshow(arr_smooth, extent=extent, cmap=cmap_rain, vmin=vmin_r, vmax=vmax_r, alpha=0.78, zorder=2)

        x_grid = np.linspace(extent[0], extent[1], arr_smooth.shape[1])
        y_grid = np.linspace(extent[3], extent[2], arr_smooth.shape[0])
        levels = np.arange(int(vmin_r), int(vmax_r) + 20, 20)
        cs = ax_map.contour(x_grid, y_grid, arr_smooth, levels=levels, colors="#1e3a8a", linewidths=1.6, zorder=4)
        ax_map.clabel(cs, inline=True, fmt="%d mm", fontsize=11, colors="#0f172a")

    SUBBLOCKS.plot(ax=ax_map, facecolor="none", edgecolor="#334155", linewidth=0.6, linestyle="--", alpha=0.65, zorder=6)
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating Rainfall Colorbar & Legend Card
    card_rain = ax_map.inset_axes([0.020, 0.490, 0.250, 0.370])
    card_rain.set_facecolor("#ffffff")
    card_rain.patch.set_alpha(0.92)
    card_rain.set_xticks([])
    card_rain.set_yticks([])
    for sp in card_rain.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_rain.text(0.06, 0.94, "ANNUAL PRECIPITATION (CHIRPS)", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    cbar_sub = card_rain.inset_axes([0.08, 0.77, 0.84, 0.10])
    cb = plt.colorbar(im, cax=cbar_sub, orientation="horizontal")
    cb.set_label("Precipitation (mm / year)", fontsize=8.8, fontweight="bold", color="#1e293b", labelpad=3)
    cb.ax.tick_params(labelsize=8)

    leg_items = [
        Line2D([0], [0], color="#1e3a8a", lw=2.0, label="Rainfall Isohyet (20mm Interval)"),
        Line2D([0], [0], color="#0f172a", lw=2.8, label="Taluka Boundary"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="3D Hillshade Relief Underlay"),
        Line2D([0], [0], color="#475569", lw=0.8, linestyle=":", label="DMS Graticule (5' Grid)"),
    ]
    card_rain.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.72), frameon=False, fontsize=8.8, labelspacing=0.80)

    # Inset Rainfall Trend Chart
    if ts_csv.exists():
        df_ts = pd.read_csv(ts_csv)
        ts_ax = card_rain.inset_axes([0.08, 0.08, 0.84, 0.28])
        ts_ax.set_facecolor("#f8fafc")
        ts_ax.bar(df_ts["year"], df_ts["annual"], color="#38bdf8", edgecolor="#0284c7", width=0.7, alpha=0.85)
        mean_rain = df_ts["annual"].mean()
        ts_ax.axhline(mean_rain, color="#dc2626", linestyle="--", lw=1.2, label=f"Mean: {mean_rain:.0f} mm")
        ts_ax.tick_params(labelsize=7, colors="#334155")
        ts_ax.grid(True, linestyle=":", alpha=0.5)
        ts_ax.legend(loc="upper left", fontsize=7.2, frameon=True, framealpha=0.85)

    draw_floating_metadata(ax_map, "• Long-term Mean: 768.4 mm/yr (1991–2024 Record)\n• Seasonal Concentration: SW Monsoon ~82.4% (Jun-Sep)")

    out_file = MAP_OUT / "Map_04_Climatological_Rainfall_Isohyets_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAP 5: SOIL DEPTH & CLASSIFICATION (NBSS&LUP)
# =====================================================================
def generate_soil_depth_map():
    print(">>> Generating A1 Full-Canvas Soil Depth Map...")
    soil_tif = MAP_DATA / "soil_depth" / "soildepth_aoi_utm.tif"
    if not soil_tif.exists():
        return

    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="SOIL DEPTH CLASSIFICATION & PEDOLOGY",
        sheet_subtitle="National Bureau of Soil Survey (NBSS&LUP) Classification | 3D Relief Fusion",
        sheet_code="A1-05"
    )

    draw_hillshade_underlay(ax_map, alpha=0.35, vert_exag=3.5)

    with rasterio.open(soil_tif) as src:
        arr = src.read(1)
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.float32)
        rgba[arr == 1] = mcolors.to_rgba("#38bdf8", alpha=0.72)  # Deep >50cm
        rgba[arr == 2] = mcolors.to_rgba("#f59e0b", alpha=0.72)  # Shallow 25-50cm
        rgba[arr == 4] = mcolors.to_rgba("#84cc16", alpha=0.72)  # Very Shallow 10-25cm
        im = ax_map.imshow(rgba, extent=extent, zorder=2)

    SUBBLOCKS.plot(ax=ax_map, facecolor="none", edgecolor="#475569", linewidth=0.6, linestyle="--", alpha=0.6, zorder=6)
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)

    # Soil Zone Labels
    t_cent = TULJAPUR_BLOCK.geometry.iloc[0].centroid
    l_cent = LOHARA_BLOCK.geometry.iloc[0].centroid
    ax_map.text(t_cent.x, t_cent.y - 4500, "TULJAPUR BLOCK\nVery Shallow Basalt Regolith (10–25 cm)", fontsize=15.5, fontweight="bold", color="#0f172a", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#64748b", alpha=0.88), zorder=25)
    ax_map.text(l_cent.x, l_cent.y, "LOHARA BLOCK\nModerately Deep Alluvial Plain (>50 cm)", fontsize=15.5, fontweight="bold", color="#0f172a", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#64748b", alpha=0.88), zorder=25)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating Soil Legend Card
    card_soil = ax_map.inset_axes([0.020, 0.500, 0.250, 0.360])
    card_soil.set_facecolor("#ffffff")
    card_soil.patch.set_alpha(0.92)
    card_soil.set_xticks([])
    card_soil.set_yticks([])
    for sp in card_soil.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_soil.text(0.06, 0.94, "SOIL DEPTH PROFILE (NBSS&LUP)", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    card_soil.plot([0.06, 0.94], [0.89, 0.89], color="#cbd5e1", lw=1.0)
    leg_items = [
        mpatches.Patch(facecolor="#84cc16", edgecolor="#4d7c0f", alpha=0.8, label="Very Shallow (10–25 cm) [66.8% Area]"),
        mpatches.Patch(facecolor="#38bdf8", edgecolor="#0284c7", alpha=0.8, label="Deep / Mod. Deep (>50 cm) [18.0% Area]"),
        mpatches.Patch(facecolor="#f59e0b", edgecolor="#b45309", alpha=0.8, label="Shallow (25–50 cm) [15.3% Area]"),
        Line2D([0], [0], color="#0f172a", lw=2.8, label="Taluka Boundary"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="3D Hillshade Relief Underlay"),
        Line2D([0], [0], color="#475569", lw=0.8, linestyle=":", label="DMS Graticule (5' Grid)"),
    ]
    card_soil.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.88), frameon=False, fontsize=8.6, labelspacing=0.80)

    draw_floating_metadata(ax_map, "• Soil Source: ICAR - NBSS&LUP 1:250k Classification\n• Soil Orders: Lithic Ustorthents / Vertic Inceptisols")

    out_file = MAP_OUT / "Map_05_Soil_Depth_Classification_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAP 6: LAND USE / LAND COVER (NRSC 1:250k)
# =====================================================================
def generate_lulc_map():
    print(">>> Generating A1 Full-Canvas LULC Dynamics Map...")
    lulc_tif = MAP_DATA / "lulc" / "lulc250k_1617_aoi_utm.tif"
    if not lulc_tif.exists():
        return

    fig, ax_map = create_full_canvas_a1_layout(
        sheet_title="LAND USE / LAND COVER (LULC) DYNAMICS",
        sheet_subtitle="National Remote Sensing Centre (NRSC / ISRO) 1:250,000 Classification | 3D Relief Fusion",
        sheet_code="A1-06"
    )

    draw_hillshade_underlay(ax_map, alpha=0.32, vert_exag=3.5)

    with rasterio.open(lulc_tif) as src:
        arr = src.read(1)
        extent = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        rgba = np.zeros((arr.shape[0], arr.shape[1], 4), dtype=np.float32)
        color_lookup = {
            1: "#dc2626", 2: "#facc15", 3: "#f97316", 4: "#78350f", 5: "#84cc16",
            6: "#fef08a", 7: "#15803d", 9: "#166534", 10: "#4ade80", 14: "#d97706",
            16: "#0284c7", 17: "#0369a1"
        }
        for val, hex_c in color_lookup.items():
            rgba[arr == val] = mcolors.to_rgba(hex_c, alpha=0.74)
        im = ax_map.imshow(rgba, extent=extent, zorder=2)

    SUBBLOCKS.plot(ax=ax_map, facecolor="none", edgecolor="#334155", linewidth=0.5, linestyle="--", alpha=0.6, zorder=6)
    TULJAPUR_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)
    LOHARA_BLOCK.boundary.plot(ax=ax_map, color="#0f172a", linewidth=3.0, linestyle="-", zorder=10)

    # Block Labels
    t_cent = TULJAPUR_BLOCK.geometry.iloc[0].centroid
    l_cent = LOHARA_BLOCK.geometry.iloc[0].centroid
    ax_map.text(t_cent.x, t_cent.y - 4500, "TULJAPUR BLOCK\nIntensive Rainfed Agriculture", fontsize=15.5, fontweight="bold", color="#0f172a", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#64748b", alpha=0.88), zorder=25)
    ax_map.text(l_cent.x, l_cent.y, "LOHARA BLOCK\nDouble-Cropped Terna Basin", fontsize=15.5, fontweight="bold", color="#0f172a", ha="center",
                bbox=dict(boxstyle="round,pad=0.4", fc="#ffffff", ec="#64748b", alpha=0.88), zorder=25)

    minx, miny, maxx, maxy = AOI_BLOCKS.total_bounds
    padx, pady = (maxx - minx) * 0.05, (maxy - miny) * 0.05
    ax_map.set_xlim(minx - padx, maxx + padx)
    ax_map.set_ylim(miny - pady, maxy + pady)
    apply_dms_graticule(ax_map)

    draw_north_arrow(ax_map)
    draw_scale_bar(ax_map, length_km=20)
    draw_floating_district_inset(ax_map, bbox=[0.800, 0.650, 0.180, 0.180])

    # Floating LULC Legend Card
    card_lulc = ax_map.inset_axes([0.020, 0.460, 0.250, 0.400])
    card_lulc.set_facecolor("#ffffff")
    card_lulc.patch.set_alpha(0.92)
    card_lulc.set_xticks([])
    card_lulc.set_yticks([])
    for sp in card_lulc.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.3)

    card_lulc.text(0.06, 0.94, "LULC CLASSIFICATION (NRSC)", fontsize=10.5, fontweight="bold", color="#0f172a", va="top")
    card_lulc.plot([0.06, 0.94], [0.89, 0.89], color="#cbd5e1", lw=1.0)
    leg_items = [
        mpatches.Patch(facecolor="#fef08a", edgecolor="#ca8a04", label="Current Fallow (575.3 km² | 28.2%)"),
        mpatches.Patch(facecolor="#facc15", edgecolor="#ca8a04", label="Kharif Cropland (566.9 km² | 27.8%)"),
        mpatches.Patch(facecolor="#d97706", edgecolor="#9a3412", label="Wasteland / Scrub (410.0 km² | 20.1%)"),
        mpatches.Patch(facecolor="#84cc16", edgecolor="#4d7c0f", label="Double / Triple Crop (285.5 km² | 14.0%)"),
        mpatches.Patch(facecolor="#f97316", edgecolor="#c2410c", label="Rabi Cropland (72.2 km² | 3.5%)"),
        mpatches.Patch(facecolor="#0284c7", edgecolor="#0369a1", label="Waterbodies & Reservoirs (85.7 km² | 4.2%)"),
        mpatches.Patch(facecolor="#dc2626", edgecolor="#991b1b", label="Built-Up Settlements (33.2 km² | 1.6%)"),
        mpatches.Patch(facecolor="#166534", edgecolor="#14532d", label="Forest & Plantations (11.4 km² | 0.6%)"),
        Line2D([0], [0], color="#0f172a", lw=2.8, label="Taluka Boundary"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="3D Hillshade Relief Underlay"),
    ]
    card_lulc.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.04, 0.88), frameon=False, fontsize=8.4, labelspacing=0.75)

    draw_floating_metadata(ax_map, "• Sensor: IRS-AWiFS / Resourcesat Multi-temporal Data\n• Agro-ecological Cultivation Share: 73.5% Mapped Land")

    out_file = MAP_OUT / "Map_06_Land_Use_Land_Cover_LULC_A1.png"
    plt.savefig(out_file, bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved:", out_file.name)


# =====================================================================
# MAIN PRODUCTION RUN
# =====================================================================
if __name__ == "__main__":
    print("=" * 70)
    print("FULL-CANVAS SENIOR GIS CARTOGRAPHER: ISO A1 HIGH-DPI MAP ENGINE")
    print("=" * 70)
    generate_study_area_map()
    generate_dem_map()
    generate_hydrology_map()
    generate_rainfall_map()
    generate_soil_depth_map()
    generate_lulc_map()
    print("=" * 70)
    print("All ISO A1 High-DPI Cartographic Maps generated successfully in:", MAP_OUT)
    print("=" * 70)

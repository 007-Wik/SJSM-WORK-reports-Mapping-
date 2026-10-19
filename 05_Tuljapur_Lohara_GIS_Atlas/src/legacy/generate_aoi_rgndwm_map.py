#!/usr/bin/env python3
"""
Master RGNDWM 250K Ground Water Prospects Grid Framework Map for the AOI
(Tuljapur and Lohara Blocks, Dharashiv / Osmanabad District, Maharashtra)

Senior Cartographer & Lead Hydrogeologist Master Atlas Edition
Canvas: Architectural D / ISO A1 Landscape (32.0 x 20.0 inches @ 300 DPI)

Features:
- Full AOI view (Tuljapur & Lohara blocks, 2,044 km², 177 villages)
- Rajiv Gandhi National Drinking Water Mission (RGNDWM) 1° x 1° Master Quadrangle Grids (NRSC / ISRO)
- Survey of India 15' x 15' Toposheet Grid Framework (1:50,000 scale) with exact sheet indexing
- Dual-pass 3D Hillshade (Copernicus GLO-30 30m) revealing basaltic flow terraces & valleys
- Complete Strahler drainage network (Orders 3 to 6) highlighting recharge channels
- Dedicated 8-inch cartographic right-hand sidebar with glassmorphic cards:
    1. Cartographic Legend
    2. 1:250k & 1:50k Toposheet Breakdown Matrix
    3. RGNDWM Hydrogeological & Recharge Planning Guide
    4. Graphical Scale Bar, Compass Rose & Technical Metadata
- Regional District Inset Map
- Precise Degrees-Minutes-Seconds (DMS) Neatline Collar
"""

from pathlib import Path
import geopandas as gpd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe
from shapely.geometry import box
import numpy as np
import rasterio
import scipy.ndimage
import pyproj

BASE_DIR = Path(__file__).resolve().parents[2]
MAP_DATA = BASE_DIR / "data" / "processed" if (BASE_DIR / "data" / "processed" / "aoi" / "aoi_blocks.gpkg").exists() else BASE_DIR / "map_data"
DATA_DIR = BASE_DIR / "data"
MAP_OUT = BASE_DIR / "map_data" / "maps"
MAP_OUT.mkdir(parents=True, exist_ok=True)

# Typography
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "DejaVu Serif", "Liberation Serif", "Times", "serif"]

HALO = [pe.withStroke(linewidth=3.5, foreground="white")]
DARK_HALO = [pe.withStroke(linewidth=3.5, foreground="#0f172a")]

# Coordinate transformers
T_WGS_TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
T_UTM_TO_WGS = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


def compute_hillshade(dem_arr, res=30.0, vert_exag=3.5, azimuth=315.0, altitude=45.0):
    """Compute high-contrast multi-directional shaded relief."""
    zenith = np.radians(90.0 - altitude)
    az_rad = np.radians(azimuth)

    dy, dx = np.gradient(dem_arr * vert_exag, res, res)
    slope = np.arctan(np.sqrt(dx * dx + dy * dy))
    aspect = np.arctan2(-dx, dy)

    shaded = np.sin(zenith) * np.cos(slope) + np.cos(zenith) * np.sin(slope) * np.cos(az_rad - aspect)
    shaded = np.clip(shaded, 0, 1)

    # Ambient second pass from 45 deg for softening basalt escarpment shadows
    az2 = np.radians(45.0)
    shaded2 = np.sin(zenith) * np.cos(slope) + np.cos(zenith) * np.sin(slope) * np.cos(az2 - aspect)
    shaded2 = np.clip(shaded2, 0, 1)

    return 0.7 * shaded + 0.3 * shaded2


def dms_str(deg_float, is_lat=True):
    d = int(deg_float)
    m = int(round((deg_float - d) * 60))
    if m == 60:
        d += 1
        m = 0
    hemi = ("N" if d >= 0 else "S") if is_lat else ("E" if d >= 0 else "W")
    return f"{abs(d)}°{m:02d}'{hemi}" if m > 0 else f"{abs(d)}°{hemi}"


def generate_aoi_rgndwm_map():
    print("=" * 70)
    print("GENERATING MASTER RGNDWM 250K GROUND WATER PROSPECTS MAP FOR AOI")
    print("=" * 70)

    # 1. Load Vector Layers
    aoi_blocks = gpd.read_file(MAP_DATA / "aoi" / "aoi_blocks.gpkg").to_crs(32643)
    aoi_union = aoi_blocks.union_all()
    tuljapur = aoi_blocks[aoi_blocks["NAME"] == "Tuljapur"]
    lohara = aoi_blocks[aoi_blocks["NAME"] == "Lohara"]

    villages = gpd.read_file(MAP_DATA / "aoi" / "subblocks_villages.gpkg").to_crs(32643)
    district_talukas = gpd.read_file(MAP_DATA / "aoi" / "osmanabad_district_talukas.gpkg").to_crs(32643) if (MAP_DATA / "aoi" / "osmanabad_district_talukas.gpkg").exists() else None
    roads = gpd.read_file(MAP_DATA / "roads" / "roads_osm.gpkg").to_crs(32643) if (MAP_DATA / "roads" / "roads_osm.gpkg").exists() else None
    streams = gpd.read_file(MAP_DATA / "streams" / "streams_strahler.gpkg").to_crs(32643) if (MAP_DATA / "streams" / "streams_strahler.gpkg").exists() else None
    geojson_path = (DATA_DIR / "raw" / "India 250k Polygon.geojson") if (DATA_DIR / "raw" / "India 250k Polygon.geojson").exists() else (DATA_DIR / "India 250k Polygon.geojson")
    rgndwm_raw = gpd.read_file(geojson_path).to_crs(32643)

    # 2. Viewport & Dimensions
    bx0, by0, bx1, by1 = aoi_blocks.total_bounds
    w_aoi = bx1 - bx0
    h_aoi = by1 - by0

    # Generous margins around AOI for regional 1° x 1° grid visibility
    pad_x = w_aoi * 0.12
    pad_y = h_aoi * 0.18
    x_min, x_max = bx0 - pad_x, bx1 + pad_x
    y_min, y_max = by0 - pad_y, by1 + pad_y

    # Canvas Setup: 32 x 20 inches @ 300 DPI
    fig = plt.figure(figsize=(32.0, 20.0), dpi=300, facecolor="#f8fafc")

    # Map axis on the left/center (leaving 26% width on the right for sidebar)
    ax = fig.add_axes([0.035, 0.045, 0.675, 0.875])
    ax.set_facecolor("#edf2f7")
    ax.set_xlim(x_min, x_max)
    ax.set_ylim(y_min, y_max)
    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])

    # 3. Read DEM & Render Hillshade
    print("Rendering 3D Shaded Relief Underlay...")
    dem_path = MAP_DATA / "dem" / "dem_buffered.tif"
    with rasterio.open(dem_path) as src:
        dem = src.read(1).astype(np.float32)
        nd = src.nodata
        if nd is not None:
            dem[dem == nd] = np.nan
        dem_clean = scipy.ndimage.gaussian_filter(np.nan_to_num(dem, nan=500.0), sigma=1.2)
        hs = compute_hillshade(dem_clean, res=src.res[0], vert_exag=3.8)
        dem_ext = [src.bounds.left, src.bounds.right, src.bounds.bottom, src.bounds.top]
        ax.imshow(hs, extent=dem_ext, cmap="gray", alpha=0.52, zorder=1, origin="upper")

    # 4. Generate 1:250k and 1:50k Toposheet Framework
    print("Constructing RGNDWM 250k & 1:50k Grid Geometries...")
    view_box = box(x_min, y_min, x_max, y_max)
    rg_clipped = gpd.clip(rgndwm_raw, view_box)

    quad_colors = {
        "56C": {"fill": "#dbeafe", "edge": "#1e3a8a"},
        "56B": {"fill": "#fef3c7", "edge": "#b45309"},
        "47O": {"fill": "#dcfce7", "edge": "#15803d"},
        "47N": {"fill": "#f3e8ff", "edge": "#7e22ce"}
    }

    # Plot 1:250k Quadrangles
    for idx, r in rg_clipped.iterrows():
        map_no = str(r["MAP_NO"])
        qcfg = quad_colors.get(map_no, {"fill": "#f1f5f9", "edge": "#334155"})
        g_series = gpd.GeoSeries([r.geometry], crs=32643)
        g_series.plot(ax=ax, facecolor=qcfg["fill"], alpha=0.35, edgecolor="none", zorder=2)

    # Construct 1:50,000 Sub-grid (15' x 15' = 0.25° x 0.25°)
    lon0, lat0 = T_UTM_TO_WGS.transform(x_min, y_min)
    lon1, lat1 = T_UTM_TO_WGS.transform(x_max, y_max)

    quad_defs = [
        ("47N", 75.0, 18.0),
        ("47O", 75.0, 17.0),
        ("56B", 76.0, 18.0),
        ("56C", 76.0, 17.0)
    ]

    subsheet_list = []
    for qname, qx0, qy0 in quad_defs:
        for row in range(4):
            lat_top = qy0 + 1.0 - row * 0.25
            lat_bot = lat_top - 0.25
            for col in range(4):
                lon_left = qx0 + col * 0.25
                lon_right = lon_left + 0.25
                sheet_num = row * 4 + col + 1
                full_code = f"{qname}/{sheet_num}"
                poly = box(lon_left, lat_bot, lon_right, lat_top)
                subsheet_list.append({
                    "code": full_code,
                    "quad": qname,
                    "num": sheet_num,
                    "lon_c": (lon_left + lon_right) / 2.0,
                    "lat_c": (lat_bot + lat_top) / 2.0,
                    "geometry": poly
                })

    gdf_subsheets = gpd.GeoDataFrame(subsheet_list, crs="EPSG:4326").to_crs(32643)
    gdf_sub_view = gpd.clip(gdf_subsheets, view_box)

    # Plot 1:50,000 Toposheet Grid Lines (thin dashed)
    gdf_sub_view.boundary.plot(ax=ax, color="#475569", linewidth=0.9, linestyle="--", alpha=0.75, zorder=4)

    # Plot 1:250,000 Quadrangle Boundaries (thick crisp lines)
    rg_clipped.boundary.plot(ax=ax, color="#1e1b4b", linewidth=2.4, linestyle="-", zorder=6)

    # 5. Plot Hydrology & Roads
    print("Plotting Drainage & Infrastructure...")
    if streams is not None:
        st_clip = gpd.clip(streams, view_box)
        st_hi = st_clip[st_clip["strahler"] >= 3]
        for ord_val, w, col in [(3, 0.7, "#7dd3fc"), (4, 1.2, "#38bdf8"), (5, 1.8, "#0284c7"), (6, 2.4, "#0369a1")]:
            sub = st_hi[st_hi["strahler"] == ord_val]
            if not sub.empty:
                sub.plot(ax=ax, color=col, linewidth=w, alpha=0.85, zorder=5)

    if roads is not None:
        rd_clip = gpd.clip(roads, view_box)
        rd_clip.plot(ax=ax, color="#fbbf24", linewidth=0.9, alpha=0.6, zorder=5)

    # 6. Plot Administrative Boundaries
    print("Plotting Administrative Layers...")
    vil_clip = gpd.clip(villages, view_box)
    vil_clip.boundary.plot(ax=ax, color="#cbd5e1", linewidth=0.5, alpha=0.7, zorder=6)

    # Block Polygons (Tuljapur & Lohara)
    tuljapur.plot(ax=ax, facecolor="#f87171", alpha=0.18, edgecolor="none", zorder=7)
    lohara.plot(ax=ax, facecolor="#60a5fa", alpha=0.18, edgecolor="none", zorder=7)

    # Strong outlines
    tuljapur.boundary.plot(ax=ax, color="#b91c1c", linewidth=2.8, linestyle="-", zorder=9)
    lohara.boundary.plot(ax=ax, color="#1d4ed8", linewidth=2.8, linestyle="-", zorder=9)

    # Complete AOI Outer Boundary
    gpd.GeoSeries([aoi_union], crs=32643).boundary.plot(ax=ax, color="#0f172a", linewidth=3.4, linestyle="-", zorder=10)

    # 7. Labels: 1:50k Sub-sheet Labels
    for idx, r in gdf_sub_view.iterrows():
        code = r["code"]
        poly = r.geometry
        cx, cy = poly.centroid.x, poly.centroid.y
        if x_min + 4000 < cx < x_max - 4000 and y_min + 4000 < cy < y_max - 4000:
            inter_aoi = poly.intersects(aoi_union)
            f_color = "#1e293b" if inter_aoi else "#64748b"
            f_weight = "bold" if inter_aoi else "normal"
            ax.text(cx, cy - 2500, code, fontsize=11, fontweight=f_weight,
                    color=f_color, ha="center", va="center", path_effects=HALO, zorder=11)

    # 8. Prominent 1:250k Quadrangle Titles
    quad_label_pos = {
        "56C": (bx0 + w_aoi * 0.70, by0 + h_aoi * 0.20),
        "56B": (bx0 + w_aoi * 0.72, by1 + pad_y * 0.45),
        "47O": (bx0 - pad_x * 0.35, by0 + h_aoi * 0.30),
        "47N": (bx0 - pad_x * 0.35, by0 + h_aoi * 0.65)
    }

    for map_no, (lx, ly) in quad_label_pos.items():
        if x_min < lx < x_max and y_min < ly < y_max:
            ax.text(lx, ly, f"RGNDWM 250K QUADRANGLE\nSHEET {map_no}",
                    fontsize=15, fontweight="bold", color="#1e1b4b", ha="center", va="center",
                    path_effects=HALO, alpha=0.88, zorder=12)

    # 9. Prominent Block Headquarters & Major Town Labels
    towns = [
        ("Tuljapur HQ\n(Taluka Center)", 609200, 1992400, "#991b1b"),
        ("Lohara HQ\n(Taluka Center)", 642800, 1993200, "#1e40af"),
        ("Naldurg\n(Historic Fort / Bori Basin)", 614800, 1968800, "#0f172a"),
        ("Kati", 627100, 1974600, "#334155"),
        ("Mangrul", 649200, 1982500, "#334155"),
        ("Javalga", 657800, 1967200, "#334155"),
        ("Tamalwadi", 595200, 1978300, "#334155"),
        ("Dharashiv (Osmanabad)\nDistrict HQ [North]", 613500, 2011000, "#0f172a"),
    ]

    for name, tx, ty, tcolor in towns:
        if x_min < tx < x_max and y_min < ty < y_max:
            ax.plot(tx, ty, marker="o", markersize=6.5, markerfacecolor=tcolor,
                    markeredgecolor="white", markeredgewidth=1.4, zorder=14)
            ax.text(tx, ty + 1200, name, fontsize=9.5, fontweight="bold",
                    color=tcolor, ha="center", va="bottom", path_effects=HALO, zorder=15)

    # Block Name Callouts
    ax.text(612000, 1983000, "TULJAPUR BLOCK\n(1,500.7 km² | 130 Villages)",
            fontsize=15, fontweight="bold", color="#991b1b", ha="center", va="center",
            path_effects=HALO, alpha=0.92, zorder=13)

    ax.text(648000, 1974000, "LOHARA BLOCK\n(543.2 km² | 47 Villages)",
            fontsize=14, fontweight="bold", color="#1e40af", ha="center", va="center",
            path_effects=HALO, alpha=0.92, zorder=13)

    # 10. Quadrangle Intersection Nexus Callout (76°00'E, 18°00'N)
    nexus_x, nexus_y = T_WGS_TO_UTM.transform(76.00, 18.00)
    ax.plot(nexus_x, nexus_y, marker="+", markersize=20, markeredgewidth=3.2,
            markeredgecolor="#dc2626", zorder=16)
    ax.text(nexus_x + 1200, nexus_y + 1200,
            "QUADRANGLE NEXUS POINT\n76°00'00\"E | 18°00'00\"N\n(Nexus of 47N, 47O, 56B, 56C)",
            fontsize=9.2, fontweight="bold", color="#b91c1c", ha="left", va="bottom",
            path_effects=HALO, zorder=16)

    # 11. Regional Location Index (Maharashtra State -> Dharashiv District with Tuljapur & Lohara highlighted)
    mh_path = DATA_DIR / "processed" / "location_index" / "maharashtra_districts.geojson"
    dh_path = DATA_DIR / "processed" / "location_index" / "dharashiv_8_tehsils.geojson"
    mh_districts = gpd.read_file(mh_path).to_crs(32643) if mh_path.exists() else None
    dharashiv_tehsils = gpd.read_file(dh_path).to_crs(32643) if dh_path.exists() else None

    if mh_districts is not None and dharashiv_tehsils is not None:
        # 1. Maharashtra Subplot
        ax_mh = ax.inset_axes([0.020, 0.720, 0.125, 0.240])
        ax_mh.patch.set_alpha(0.0)
        ax_mh.set_aspect("equal")
        ax_mh.axis("off")
        for sp in ax_mh.spines.values():
            sp.set_visible(False)

        mh_districts.plot(ax=ax_mh, facecolor="none", edgecolor="#64748b", linewidth=0.5)
        mh_districts[mh_districts["NAME_2"].str.contains("Osmanabad|Dharashiv", case=False, na=False)].plot(
            ax=ax_mh, facecolor="#c1121f", edgecolor="#7f1d1d", linewidth=0.9
        )
        ax_mh.text(0.5, 1.04, "MAHARASHTRA STATE", transform=ax_mh.transAxes, fontsize=8.5, fontweight="bold",
                   ha="center", va="bottom", color="#0f172a", path_effects=HALO)

        # 2. Dharashiv District Subplot
        ax_dist = ax.inset_axes([0.155, 0.720, 0.135, 0.240])
        ax_dist.patch.set_alpha(0.0)
        ax_dist.set_aspect("equal")
        ax_dist.axis("off")
        for sp in ax_dist.spines.values():
            sp.set_visible(False)

        dharashiv_tehsils.plot(ax=ax_dist, facecolor="none", edgecolor="#64748b", linewidth=0.6)

        # Highlight both study area blocks
        poly_tul = dharashiv_tehsils[dharashiv_tehsils["TALUKA"].str.lower() == "tuljapur"]
        poly_loh = dharashiv_tehsils[dharashiv_tehsils["TALUKA"].str.lower() == "lohara"]

        poly_tul.plot(ax=ax_dist, facecolor="#c1121f", edgecolor="#7f1d1d", linewidth=1.1)
        poly_loh.plot(ax=ax_dist, facecolor="#1d4ed8", edgecolor="#1e3a8a", linewidth=1.1)

        for _, r in dharashiv_tehsils.iterrows():
            t = r["TALUKA"]
            c = r.geometry.centroid
            if t.lower() == "tuljapur":
                ax_dist.text(c.x, c.y, t, fontsize=7.2, fontweight="bold",
                             color="#ffffff", ha="center", va="center",
                             path_effects=[pe.withStroke(linewidth=1.6, foreground="#7f1d1d")])
            elif t.lower() == "lohara":
                ax_dist.text(c.x, c.y, t, fontsize=7.2, fontweight="bold",
                             color="#ffffff", ha="center", va="center",
                             path_effects=[pe.withStroke(linewidth=1.6, foreground="#1e3a8a")])
            else:
                ax_dist.text(c.x, c.y, t, fontsize=5.0, color="#475569",
                             ha="center", va="center", path_effects=[pe.withStroke(linewidth=1.2, foreground="white")])

        ax_dist.text(0.5, 1.04, "DHARASHIV DISTRICT", transform=ax_dist.transAxes, fontsize=8.5, fontweight="bold",
                     ha="center", va="bottom", color="#0f172a", path_effects=HALO)

    # 12. DMS Graticule Tick Labels along the neatline
    print("Formatting Neatline DMS Graticule...")
    lon_ticks = np.arange(np.floor(lon0 * 4) / 4, np.ceil(lon1 * 4) / 4 + 0.01, 0.25)
    lat_ticks = np.arange(np.floor(lat0 * 4) / 4, np.ceil(lat1 * 4) / 4 + 0.01, 0.25)

    for lon in lon_ticks:
        tx, ty = T_WGS_TO_UTM.transform(lon, lat0)
        if x_min <= tx <= x_max:
            ax.plot([tx, tx], [y_min, y_min + 1800], color="#0f172a", lw=1.2, zorder=20)
            ax.text(tx, y_min + 2200, dms_str(lon, is_lat=False), fontsize=9, fontweight="bold",
                    color="#0f172a", ha="center", va="bottom", path_effects=HALO, zorder=20)

            tx_top, ty_top = T_WGS_TO_UTM.transform(lon, lat1)
            ax.plot([tx_top, tx_top], [y_max, y_max - 1800], color="#0f172a", lw=1.2, zorder=20)
            ax.text(tx_top, y_max - 2200, dms_str(lon, is_lat=False), fontsize=9, fontweight="bold",
                    color="#0f172a", ha="center", va="top", path_effects=HALO, zorder=20)

    for lat in lat_ticks:
        tx_l, ty_l = T_WGS_TO_UTM.transform(lon0, lat)
        if y_min <= ty_l <= y_max:
            ax.plot([x_min, x_min + 1800], [ty_l, ty_l], color="#0f172a", lw=1.2, zorder=20)
            ax.text(x_min + 2200, ty_l, dms_str(lat, is_lat=True), fontsize=9, fontweight="bold",
                    color="#0f172a", ha="left", va="center", path_effects=HALO, zorder=20)

            tx_r, ty_r = T_WGS_TO_UTM.transform(lon1, lat)
            ax.plot([x_max, x_max - 1800], [ty_r, ty_r], color="#0f172a", lw=1.2, zorder=20)
            ax.text(x_max - 2200, ty_r, dms_str(lat, is_lat=True), fontsize=9, fontweight="bold",
                    color="#0f172a", ha="right", va="center", path_effects=HALO, zorder=20)

    # Outer neatline frame
    for spine in ax.spines.values():
        spine.set_color("#0f172a")
        spine.set_linewidth(2.2)

    # =========================================================================
    # HEADER TITLE BANNER
    # =========================================================================
    title_ax = fig.add_axes([0.035, 0.932, 0.930, 0.055])
    title_ax.set_facecolor("#1e1b4b")
    title_ax.set_xticks([])
    title_ax.set_yticks([])
    for sp in title_ax.spines.values():
        sp.set_color("#0f172a")
        sp.set_linewidth(1.8)

    title_ax.text(0.50, 0.68, "RAJIV GANDHI NATIONAL DRINKING WATER MISSION (RGNDWM) 250K FRAMEWORK",
                  fontsize=18, fontweight="bold", color="#ffffff", ha="center", va="center")
    title_ax.text(0.50, 0.26, "Ground Water Prospects 1° × 1° Quadrangle Grid Index & Survey of India 1:50,000 Toposheet Hydrogeological Reference for AOI",
                  fontsize=12, fontweight="normal", color="#cbd5e1", ha="center", va="center")

    # =========================================================================
    # DEDICATED RIGHT-HAND CARTOGRAPHIC SIDEBAR (4 CARDS)
    # =========================================================================
    sb_x0 = 0.725
    sb_w = 0.240

    # 1. Legend Card
    card_leg = fig.add_axes([sb_x0, 0.640, sb_w, 0.280])
    card_leg.set_facecolor("#ffffff")
    card_leg.set_xticks([])
    card_leg.set_yticks([])
    card_leg.set_xlim(0, 1)
    card_leg.set_ylim(0, 1)
    for sp in card_leg.spines.values():
        sp.set_color("#1e1b4b")
        sp.set_linewidth(1.3)

    card_leg.text(0.05, 0.95, "CARTOGRAPHIC MAP LEGEND", fontsize=11, fontweight="bold", color="#1e1b4b", va="top")
    card_leg.plot([0.05, 0.95], [0.90, 0.90], color="#94a3b8", lw=1.0)
    card_leg.set_xlim(0, 1)
    card_leg.set_ylim(0, 1)

    leg_items = [
        Line2D([0], [0], color="#0f172a", lw=3.0, label="Study Area Boundary (AOI: 2,044 km²)"),
        Line2D([0], [0], color="#b91c1c", lw=2.2, label="Tuljapur Taluka (1,500.7 km²)"),
        Line2D([0], [0], color="#1d4ed8", lw=2.2, label="Lohara Taluka (543.2 km²)"),
        Line2D([0], [0], color="#cbd5e1", lw=0.8, label="Village Cadastral Boundaries (177 Units)"),
        Line2D([0], [0], color="#1e1b4b", lw=2.2, label="RGNDWM 1° × 1° Quadrangle (250k)"),
        Line2D([0], [0], color="#475569", lw=1.1, ls="--", label="SOI 15' × 15' Toposheet Grid (50k)"),
        mpatches.Patch(facecolor="#dbeafe", edgecolor="#1e3a8a", alpha=0.5, label="Sheet 56C (Sholapur / Osmanabad Quad)"),
        mpatches.Patch(facecolor="#fef3c7", edgecolor="#b45309", alpha=0.5, label="Sheet 56B (Bidar / Latur Quad)"),
        mpatches.Patch(facecolor="#dcfce7", edgecolor="#15803d", alpha=0.5, label="Sheet 47O (Solapur / Sina Basin Quad)"),
        mpatches.Patch(facecolor="#f3e8ff", edgecolor="#7e22ce", alpha=0.5, label="Sheet 47N (Beed / Godavari Fringe Quad)"),
        Line2D([0], [0], color="#0284c7", lw=1.8, label="Major Drainage Channel (Order 4–6)"),
        Line2D([0], [0], color="#7dd3fc", lw=1.0, label="Tributary Streams (Order 3)"),
        Line2D([0], [0], color="#fbbf24", lw=1.1, label="Road Transport Network (OSM)"),
        Line2D([0], [0], marker="o", color="w", markerfacecolor="#991b1b", markersize=6.5, label="Taluka Headquarters / Major Settlement"),
        Line2D([0], [0], marker="+", color="#dc2626", markersize=9, markeredgewidth=2, label="Nexus Point (76°E, 18°N)"),
        mpatches.Patch(facecolor="#94a3b8", edgecolor="none", alpha=0.5, label="Copernicus GLO-30 3D Shaded Relief"),
    ]
    card_leg.legend(handles=leg_items, loc="upper left", bbox_to_anchor=(0.02, 0.89),
                    frameon=False, fontsize=8.0, labelspacing=0.48)

    # 2. Toposheet & Quadrangle Allocation Table Card
    card_tbl = fig.add_axes([sb_x0, 0.365, sb_w, 0.260])
    card_tbl.set_facecolor("#ffffff")
    card_tbl.set_xticks([])
    card_tbl.set_yticks([])
    for sp in card_tbl.spines.values():
        sp.set_color("#1e1b4b")
        sp.set_linewidth(1.3)

    card_tbl.text(0.05, 0.95, "AOI TOPOSHEET & QUADRANGLE COVERAGE", fontsize=11, fontweight="bold", color="#1e1b4b", va="top")
    card_tbl.plot([0.05, 0.95], [0.90, 0.90], color="#94a3b8", lw=1.0)
    card_tbl.set_xlim(0, 1)
    card_tbl.set_ylim(0, 1)

    tbl_text = (
        "1° × 1° Quadrangle Breakdown (Total AOI = 2,043.9 km²):\n"
        "───────────────────────────────────────────────\n"
        "Sheet 56C (Sholapur/Osmanabad) : 1,433.9 km² (70.1%)\n"
        "  • Tuljapur: 1,069.6 km² | Lohara: 364.3 km²\n"
        "  • 1:50k Sheets: 56C/1 (699.1 km²), 56C/2 (551.0 km²),\n"
        "                  56C/6 (97.4 km²), 56C/5 (63.8 km²), 56C/3 (22.5 km²)\n\n"
        "Sheet 56B (Bidar/Latur)         :   340.1 km² (16.6%)\n"
        "  • Tuljapur: 161.2 km²  | Lohara: 178.9 km²\n"
        "  • 1:50k Sheets: 56B/13 (163.2 km²), 56B/14 (152.7 km²),\n"
        "                  56B/15 (24.4 km²)\n\n"
        "Sheet 47O (Solapur/Sina Basin)  :   262.8 km² (12.9%)\n"
        "  • Tuljapur West | 1:50k Sheet: 47O/4 (262.7 km²)\n\n"
        "Sheet 47N (Beed/Sina Fringe)    :     7.1 km² ( 0.4%)\n"
        "  • Tuljapur NW Ridge | 1:50k Sheet: 47N/16 (7.2 km²)\n"
        "───────────────────────────────────────────────\n"
        "Total 1:50,000 Prospect Maps Covering Study Area: 10 Sheets"
    )
    card_tbl.text(0.05, 0.86, tbl_text, fontsize=7.8, color="#0f172a", va="top", linespacing=1.24)

    # 3. RGNDWM Hydrogeological & Recharge Planning Guide Card
    card_info = fig.add_axes([sb_x0, 0.155, sb_w, 0.195])
    card_info.set_facecolor("#ffffff")
    card_info.set_xticks([])
    card_info.set_yticks([])
    for sp in card_info.spines.values():
        sp.set_color("#1e1b4b")
        sp.set_linewidth(1.3)

    card_info.text(0.05, 0.94, "RGNDWM HYDROGEOLOGY & RECHARGE", fontsize=11, fontweight="bold", color="#1e1b4b", va="top")
    card_info.plot([0.05, 0.95], [0.88, 0.88], color="#94a3b8", lw=1.0)
    card_info.set_xlim(0, 1)
    card_info.set_ylim(0, 1)

    info_text = (
        "• Mission Mandate (NRSC / ISRO & MDWS):\n"
        "  Provides space-based hydrogeomorphological and structural\n"
        "  mapping for identifying sustainable rural drinking water sources.\n\n"
        "• Hard-Rock Basaltic Hydrogeology (Deccan Traps AOI):\n"
        "  Ground water occurrence is strictly controlled by vesicular\n"
        "  flow tops, jointing, and weathered sheet depth (5–25 m bgl).\n\n"
        "• Artificial Recharge Interventions Recommended by NRSC:\n"
        "  1. Percolation Tanks & Check Dams on 3rd–4th order streams\n"
        "  2. Subsurface Dykes in valley fills to arrest baseflow egress\n"
        "  3. Continuous Contour Trenches (CCT) & Farm Ponds on plateaus"
    )
    card_info.text(0.05, 0.83, info_text, fontsize=8.0, color="#1e293b", va="top", linespacing=1.25)

    # 4. Scale Bar, Compass Rose & Metadata Card
    card_meta = fig.add_axes([sb_x0, 0.045, sb_w, 0.095])
    card_meta.set_facecolor("#ffffff")
    card_meta.set_xticks([])
    card_meta.set_yticks([])
    for sp in card_meta.spines.values():
        sp.set_color("#1e1b4b")
        sp.set_linewidth(1.3)
    card_meta.set_xlim(0, 1)
    card_meta.set_ylim(0, 1)

    # Inset axis for perfectly circular compass rose
    ax_compass = card_meta.inset_axes([0.80, 0.10, 0.18, 0.80])
    ax_compass.set_aspect("equal")
    ax_compass.set_xlim(-1.2, 1.2)
    ax_compass.set_ylim(-1.2, 1.2)
    ax_compass.axis("off")

    c_circle = plt.Circle((0, 0), 0.95, fill=False, edgecolor="#0f172a", lw=1.3)
    ax_compass.add_patch(c_circle)
    ax_compass.fill([0, -0.22, 0], [0, 0, 0.90], color="#0f172a")
    ax_compass.fill([0, 0.22, 0], [0, 0, 0.90], color="#94a3b8")
    ax_compass.fill([0, -0.22, 0], [0, 0, -0.90], color="#cbd5e1")
    ax_compass.fill([0, 0.22, 0], [0, 0, -0.90], color="#e2e8f0")
    ax_compass.text(0, 1.05, "N", fontsize=9.5, fontweight="bold", ha="center", va="bottom", color="#0f172a")

    # 4-Segment Scale Bar
    sb_x0_val = 0.05
    sb_y0_val = 0.56
    sb_w_val = 0.68
    sb_h_val = 0.16
    seg_w = sb_w_val / 4.0

    for i in range(4):
        fcol = "#0f172a" if i % 2 == 0 else "#ffffff"
        card_meta.add_patch(mpatches.Rectangle((sb_x0_val + i * seg_w, sb_y0_val), seg_w, sb_h_val,
                                               facecolor=fcol, edgecolor="#0f172a", lw=1.0))
        card_meta.text(sb_x0_val + i * seg_w, sb_y0_val - 0.08, f"{i * 5}", fontsize=7.2, ha="center", va="top")
    card_meta.text(sb_x0_val + 4 * seg_w, sb_y0_val - 0.08, "20 km", fontsize=7.2, ha="center", va="top")
    card_meta.text(sb_x0_val + sb_w_val / 2.0, sb_y0_val + sb_h_val + 0.05, "SCALE 1 : 125,000", fontsize=8.2, fontweight="bold", ha="center", va="bottom")

    meta_desc = (
        "• CRS: WGS 84 / UTM Zone 43N (EPSG: 32643) | Grid: SOI 15' Toposheets\n"
        "• Data Source: NRSC / ISRO & Ministry of Drinking Water & Sanitation"
    )
    card_meta.text(0.05, 0.18, meta_desc, fontsize=7.2, color="#334155", va="top", linespacing=1.2)

    # Save High-DPI Output
    out_file = MAP_OUT / "AOI_RGNDWM_250k_Ground_Water_Prospects_Framework_Map.png"
    deliv_file = BASE_DIR / "deliverables" / "maps" / "AOI_RGNDWM_250k_Ground_Water_Prospects_Framework_Map.png"
    deliv_file.parent.mkdir(parents=True, exist_ok=True)
    
    print(f"Saving high-resolution cartographic master: {out_file}...")
    plt.savefig(out_file, dpi=300, bbox_inches="tight")
    plt.savefig(deliv_file, dpi=300, bbox_inches="tight")
    plt.close()
    print("SUCCESS: Master AOI RGNDWM 250k Map Created!")


if __name__ == "__main__":
    generate_aoi_rgndwm_map()

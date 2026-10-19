#!/usr/bin/env python3
"""
Stage 03: Cartographic Production Engine - 300 DPI Transparent-Legend Block & Atlas Maps.
Preserves the exact production cartography layout, color codes, and symbology of Lohara
applied to Tuljapur and Lohara blocks across all 16 thematic layers:
 1. Study Area & Village Cadastral Map
 2. 10m High-Resolution Contour Map
 3. Annual Land Use / Land Cover Map (NRSC Bhuvan 10m/250k)
 4. Soil Depth Classification Map (NBSS&LUP)
 5. Road Transportation Network Map (OSM)
 6. Rainfall Isohyet Map (CHIRPS / IMD)
 7. Observed Lithology & Regional CGWB Litholog Map
 8. Digital Elevation Model Map (Copernicus GLO-30)
 9. Administrative Village Boundary Map
 10. Slope Percentage Map
 11. Drainage Network & Strahler Stream Order Map
 12. Seasonal NDVI Vegetation Health Map
 13. Soil Texture Classification Map
 14. Geomorphological Units Map
 15. RGNDWM 250k Ground Water Prospects Grid Framework Map
 16. Continuous Drainage Density Heatmap (50m KDE)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import geopandas as gpd
import numpy as np
import pyproj
import rasterio
import scipy.ndimage
from matplotlib.path import Path as MPath
from rasterio.mask import mask
from shapely.geometry import box

try:
    from adjustText import adjust_text
except ImportError:
    adjust_text = None

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_PROC = BASE_DIR / "data" / "processed" if (BASE_DIR / "data" / "processed" / "aoi" / "aoi_blocks.gpkg").exists() else BASE_DIR / "map_data"
DATA_RAW = BASE_DIR / "data" / "raw" if (BASE_DIR / "data" / "raw" / "India 250k Polygon.geojson").exists() else BASE_DIR / "data"
DELIV_DIR = BASE_DIR / "deliverables"
MAPS_DIR = DELIV_DIR / "maps"

# ---------------------------------------------------------------- style
plt.rcParams["font.family"] = "serif"
plt.rcParams["font.serif"] = ["Times New Roman", "Liberation Serif", "DejaVu Serif", "serif"]
plt.rcParams["axes.linewidth"] = 0.9

RED = "#c1121f"
INK = "#1a1a1a"
GREY = "#6b7280"
DOT = "#262626"
HALO = [pe.withStroke(linewidth=2.2, foreground="white")]
SUBTITLE = "Dharashiv (Osmanabad) District, Maharashtra"

# sheet geometry (inches)
MAP_MAX_W, MAP_MAX_H, MAP_MIN_W = 9.0, 11.0, 6.5
M_LEFT, M_RIGHT, M_TOP, M_BOTTOM = 0.65, 0.65, 1.60, 0.60
PAD_FRAC = 0.03

# ---------------------------------------------------------------- data
def _read(p):
    return gpd.read_file(p).to_crs("EPSG:32643") if p.exists() else None

AOI_BLOCKS = _read(DATA_PROC / "aoi" / "aoi_blocks.gpkg")
SUBBLOCKS = _read(DATA_PROC / "aoi" / "subblocks_villages.gpkg")
ROADS = _read(DATA_PROC / "roads" / "roads_osm.gpkg")
WELLS = _read(DATA_PROC / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg")
CONTOURS = _read(DATA_PROC / "dem" / "contours_10m.gpkg")
STREAMS = _read(DATA_PROC / "streams" / "streams_complete_strahler.gpkg")
DRAINAGE_DENSITY = _read(DATA_PROC / "streams" / "drainage_density_grid.gpkg")
RGNDWM_GRIDS = _read(DATA_RAW / "India 250k Polygon.geojson")
MH_DISTRICTS = gpd.read_file(DATA_PROC / "location_index" / "maharashtra_districts.geojson") if (DATA_PROC / "location_index" / "maharashtra_districts.geojson").exists() else None
DHARASHIV_TEHSILS = gpd.read_file(DATA_PROC / "location_index" / "dharashiv_8_tehsils.geojson") if (DATA_PROC / "location_index" / "dharashiv_8_tehsils.geojson").exists() else None

TO_UTM = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True)
TO_WGS = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True)


# ---------------------------------------------------------------- helpers
def geom_to_path(geom):
    verts, codes = [], []
    for poly in getattr(geom, "geoms", [geom]):
        for ring in [poly.exterior, *poly.interiors]:
            xy = np.asarray(ring.coords)
            verts.extend(xy)
            codes.extend([MPath.MOVETO] + [MPath.LINETO] * (len(xy) - 2) + [MPath.CLOSEPOLY])
    return MPath(verts, codes)


def clip_to_geom(artist, ax, geom):
    patch = mpatches.PathPatch(geom_to_path(geom), transform=ax.transData, fc="none", ec="none")
    try:
        artist.set_clip_path(patch)
    except AttributeError:
        for c in artist.collections:
            c.set_clip_path(patch)


def clipped(path, geom, nodata=None, band=0, buffer=0):
    with rasterio.open(path) as src:
        g = geom.buffer(buffer) if buffer else geom
        kw = {} if nodata is None else {"nodata": nodata}
        out_img, out_tr = mask(src, [g], crop=True, **kw)
        arr = out_img[band].astype("float32")
        nd = src.nodata if nodata is None else nodata
        if nd is not None:
            arr[arr == nd] = np.nan
        extent = (out_tr[2], out_tr[2] + out_tr[0] * arr.shape[1],
                  out_tr[5] + out_tr[4] * arr.shape[0], out_tr[5])
        return arr, extent


def clipped_rgba(path, geom):
    with rasterio.open(path) as src:
        out, tr = mask(src, [geom], crop=True)
    arr = out.transpose(1, 2, 0)
    extent = [tr.c, tr.c + tr.a * arr.shape[1], tr.f + tr.e * arr.shape[0], tr.f]
    return arr, extent


def hillshade(ax, geom, alpha=0.5, vert_exag=3.5, zorder=1):
    p = DATA_PROC / "dem" / "dem_aoi.tif"
    if not p.exists():
        return
    arr, ext = clipped(p, geom, nodata=-9999)
    dem = arr.astype("float32")
    bad = ~np.isfinite(dem) | (dem < -500)
    dem[bad] = np.nanmin(dem[~bad])
    hs = mcolors.LightSource(azdeg=315, altdeg=45).hillshade(dem, vert_exag=vert_exag)
    rgba = plt.cm.gray(0.25 + 0.75 * hs)
    rgba[..., 3] = np.where(bad, 0.0, alpha)
    im = ax.imshow(rgba, extent=ext, zorder=zorder, interpolation="bilinear")
    clip_to_geom(im, ax, geom)


def villages(name):
    v = SUBBLOCKS[SUBBLOCKS["BLOCK"] == name].copy()
    v["pt"] = v.geometry.representative_point()
    return v


def halo_labels(ax, pts, size=6.3, color=INK, pointers=True):
    texts = [ax.text(x, y, s, fontsize=size, ha="center", va="center", color=color,
                     path_effects=HALO, zorder=12) for x, y, s in pts]
    if adjust_text and texts:
        try:
            adjust_text(texts, ax=ax, expand=(1.2, 1.4),
                        arrowprops=dict(arrowstyle="-", color="#777777", lw=0.4) if pointers else None)
        except TypeError:
            adjust_text(texts, ax=ax)
    return texts


def village_labels(ax, sv, size=5.8):
    x0, x1 = ax.get_xlim(); y0, y1 = ax.get_ylim()
    inside = sv[sv["pt"].apply(lambda p: x0 <= p.x <= x1 and y0 <= p.y <= y1)].copy()
    ax.scatter([p.x for p in inside["pt"]], [p.y for p in inside["pt"]],
               s=7, color=DOT, edgecolors="white", linewidths=0.5, zorder=11)
    pts = []
    for _, r in inside.iterrows():
        name = str(r.get("VILLAGE", "")).strip().title()
        if name:
            pts.append((r["pt"].x, r["pt"].y + 160, name))
    halo_labels(ax, pts, size=size, color=INK)


def overlay_villages(ax, name):
    sv = villages(name)
    sv.boundary.plot(ax=ax, color="#475569", linewidth=0.45, linestyle="--", alpha=0.85, zorder=6)
    village_labels(ax, sv)


# ---------------------------------------------------------------- legend entry makers
def line(label, color, lw=1.5, ls="-"):
    return ("line", dict(color=color, lw=lw, ls=ls), label)

def patch(label, fc, ec="none"):
    return ("patch", dict(fc=fc, ec=ec), label)

def dot(label, color=DOT):
    return ("point", dict(color=color), label)


# ---------------------------------------------------------------- map furniture (transparent)
def legend_el(title, entries, fs=8.5):
    rh, pad, sw, th = 0.21, 0.13, 0.36, 0.30
    w = max(pad * 2 + sw + 0.10 + max(len(e[2]) for e in entries) * 0.068, pad * 2 + len(title) * 0.09)
    h = pad + th + rh * len(entries) + pad * 0.6

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        ia.text(pad, h - pad - 0.08, title, fontsize=fs + 1.5, fontweight="bold", va="center", ha="left", color=INK, path_effects=HALO)
        for i, (kind, st, label) in enumerate(entries):
            y = h - pad - th - rh * (i + 0.5)
            if kind == "line":
                ia.plot([pad, pad + sw], [y, y], color=st["color"], lw=st["lw"], ls=st["ls"], solid_capstyle="butt")
            elif kind == "patch":
                ia.add_patch(mpatches.Rectangle((pad, y - 0.06), sw, 0.12, fc=st["fc"], ec=st["ec"], lw=0.5))
            else:
                ia.plot([pad + sw / 2], [y], "o", color=st["color"], ms=4.5, mec="white", mew=0.6)
            ia.text(pad + sw + 0.10, y, label, fontsize=fs, va="center_baseline", ha="left", color=INK, path_effects=HALO)
    return w, h, draw


def scalebar_el(ax):
    fig, pos = ax.figure, ax.get_position()
    aw = pos.width * fig.get_figwidth()
    x0, x1 = ax.get_xlim()
    mpi = (x1 - x0) / aw
    target = 2.4 * mpi
    km = max([k for k in (2, 4, 8, 10, 12, 20, 40, 80) if k * 1000 <= target] or [2])
    bar = km * 1000 / mpi
    ox = 0.12
    w = ox + bar + 0.45
    h = 1.30

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        # 1. Scale bar on top
        sb_y = h - 0.28
        seg = bar / 4
        for i in range(4):
            ia.add_patch(mpatches.Rectangle((ox + i * seg, sb_y), seg, 0.08,
                                            fc="black" if i % 2 == 0 else "white", ec="black", lw=0.7))
        for frac, lab in ((0, "0"), (0.5, f"{km // 2}"), (1, f"{km} km")):
            ia.text(ox + frac * bar, sb_y + 0.12, lab, fontsize=7.5, ha="center", va="bottom", color=INK,
                    path_effects=HALO)

        # 2. North arrow directly below scale bar
        c = ox + bar / 2
        arrow_top = sb_y - 0.22
        arrow_bot = arrow_top - 0.48
        arrow_mid = arrow_top - 0.36
        dx = 0.11
        ia.add_patch(mpatches.Polygon([(c, arrow_top), (c - dx, arrow_bot), (c, arrow_mid)], fc="black", ec="black", lw=0.7))
        ia.add_patch(mpatches.Polygon([(c, arrow_top), (c + dx, arrow_bot), (c, arrow_mid)], fc="white", ec="black", lw=0.7))
        ia.text(c, arrow_top + 0.03, "N", fontsize=11, fontweight="bold", ha="center", va="bottom", color=INK, path_effects=HALO)
    return w, h, draw


def location_index_el(block_name="Tuljapur"):
    w, h = 3.60, 1.55
    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        
        y_bottom = 0.02
        box_h = h - 0.28
        box_w = (w - 0.24) / 2.0
        
        # 1. Maharashtra Subplot (State -> District, borderless & transparent)
        x0 = 0.04
        ax_mh = ia.inset_axes([x0 / w, y_bottom / h, box_w / w, box_h / h])
        ax_mh.patch.set_alpha(0.0); ax_mh.axis("off")
        for sp in ax_mh.spines.values():
            sp.set_visible(False)
        if MH_DISTRICTS is not None:
            MH_DISTRICTS.plot(ax=ax_mh, facecolor="none", edgecolor="#64748b", linewidth=0.4)
            MH_DISTRICTS[MH_DISTRICTS["NAME_2"].str.contains("Osmanabad|Dharashiv", case=False, na=False)].plot(
                ax=ax_mh, facecolor=RED, edgecolor="#7f1d1d", linewidth=0.8
            )
        ax_mh.text(0.5, 1.04, "MAHARASHTRA STATE", transform=ax_mh.transAxes, fontsize=6.8, fontweight="bold",
                    ha="center", va="bottom", color=INK, path_effects=HALO)
        
        # 2. Dharashiv District Subplot (District -> Study Block, borderless & transparent)
        x1 = x0 + box_w + 0.12
        ax_dist = ia.inset_axes([x1 / w, y_bottom / h, box_w / w, box_h / h])
        ax_dist.patch.set_alpha(0.0); ax_dist.axis("off")
        for sp in ax_dist.spines.values():
            sp.set_visible(False)
        if DHARASHIV_TEHSILS is not None:
            DHARASHIV_TEHSILS.plot(ax=ax_dist, facecolor="none", edgecolor="#64748b", linewidth=0.5)
            target_poly = DHARASHIV_TEHSILS[DHARASHIV_TEHSILS["TALUKA"].str.lower() == block_name.lower()]
            target_poly.plot(ax=ax_dist, facecolor=RED, edgecolor="#7f1d1d", linewidth=0.9)
            for _, r in DHARASHIV_TEHSILS.iterrows():
                t = r["TALUKA"]
                c = r.geometry.centroid
                if t.lower() == block_name.lower():
                    ax_dist.text(c.x, c.y, t, fontsize=6.2, fontweight="bold",
                                 color="#ffffff", ha="center", va="center",
                                 path_effects=[pe.withStroke(linewidth=1.4, foreground="#7f1d1d")])
                else:
                    ax_dist.text(c.x, c.y, t, fontsize=4.2, color="#475569",
                                 ha="center", va="center", path_effects=[pe.withStroke(linewidth=1.0, foreground="white")])
        ax_dist.text(0.5, 1.05, "DHARASHIV DISTRICT", transform=ax_dist.transAxes, fontsize=6.8, fontweight="bold",
                    ha="center", va="bottom", color=INK, path_effects=HALO)
    return w, h, draw


def elev_el(vmin, vmax, cmap, title="Elevation (m a.s.l.)"):
    w, h = 2.4, 0.62

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        ia.text(0.13, h - 0.14, title, fontsize=9, fontweight="bold", va="center", ha="left", color=INK, path_effects=HALO)
        ia.imshow(np.linspace(0, 1, 256)[None, :], extent=(0.13, w - 0.13, 0.22, 0.34),
                  cmap=cmap, aspect="auto", zorder=2)
        ia.add_patch(mpatches.Rectangle((0.13, 0.22), w - 0.26, 0.12, fc="none", ec="#475569", lw=0.6, zorder=3))
        ia.set_xlim(0, w); ia.set_ylim(0, h); ia.set_aspect("auto")
        for f in (0, 0.5, 1):
            ia.text(0.13 + f * (w - 0.26), 0.17, f"{vmin + f * (vmax - vmin):.0f}", fontsize=7.5,
                    ha="center", va="top", color=INK, path_effects=HALO)
    return w, h, draw


def density_cbar_el(vmin=0.0, vmax=3.0, cmap="YlGnBu", title="Drainage Density (km / km²)"):
    w, h = 2.4, 0.62

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        ia.text(0.13, h - 0.14, title, fontsize=8.5, fontweight="bold", va="center", ha="left", color=INK, path_effects=HALO)
        gradient = np.linspace(0, 1, 256)[None, :]
        ia.imshow(gradient, extent=(0.13, w - 0.13, 0.22, 0.34), cmap=cmap, aspect="auto", zorder=2)
        ia.add_patch(mpatches.Rectangle((0.13, 0.22), w - 0.26, 0.12, fc="none", ec="#475569", lw=0.6, zorder=3))
        ia.set_xlim(0, w); ia.set_ylim(0, h); ia.set_aspect("auto")
        for val in [0.0, 1.0, 2.0, 3.0]:
            frac = (val - vmin) / (vmax - vmin)
            if 0.0 <= frac <= 1.0:
                pos_x = 0.13 + frac * (w - 0.26)
                label = f"{val:.1f}" if val < vmax else f"{val:.1f}+"
                ia.text(pos_x, 0.17, label, fontsize=7.2, ha="center", va="top", color=INK, path_effects=HALO)
    return w, h, draw


def place_elements(ax, geom, elements):
    fig, pos = ax.figure, ax.get_position()
    aw, ah = pos.width * fig.get_figwidth(), pos.height * fig.get_figheight()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    sx, sy = (x1 - x0) / aw, (y1 - y0) / ah
    m, pad = 0.12, 0.10
    free = ["ur", "ul", "ll", "lr"]
    for w, h, draw in elements:
        best = None
        for c in free:
            xa = m if c[1] == "l" else aw - m - w
            ya = m if c[0] == "l" else ah - m - h
            bx = box(x0 + (xa - pad) * sx, y0 + (ya - pad) * sy, x0 + (xa + w + pad) * sx, y0 + (ya + h + pad) * sy)
            ov = geom.intersection(bx).area
            if best is None or ov < best[0] - 1e-9:
                best = (ov, c, xa, ya)
        _, c, xa, ya = best
        free.remove(c)
        ia = ax.inset_axes([xa / aw, ya / ah, w / aw, h / ah])
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        ia.set_xlim(0, w); ia.set_ylim(0, h); ia.axis("off"); ia.set_zorder(30)
        draw(ia, w, h)


def dms_ticks(ax):
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    cs = [TO_WGS.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    lons, lats = [c[0] for c in cs], [c[1] for c in cs]
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    span = max(lo1 - lo0, la1 - la0) * 60
    step = next((s for s in (1, 2, 5, 10, 15, 30) if span / s <= 8), 10)
    xt, xl, yt, yl = [], [], [], []
    for m in range(int(np.ceil(lo0 * 60 / step)) * step, int(np.floor(lo1 * 60 / step)) * step + 1, step):
        x = TO_UTM.transform(m / 60, (la0 + la1) / 2)[0]
        if x0 <= x <= x1:
            xt.append(x); xl.append(f"{m // 60}°{m % 60:02d}′E")
    for m in range(int(np.ceil(la0 * 60 / step)) * step, int(np.floor(la1 * 60 / step)) * step + 1, step):
        y = TO_UTM.transform((lo0 + lo1) / 2, m / 60)[1]
        if y0 <= y <= y1:
            yt.append(y); yl.append(f"{m // 60}°{m % 60:02d}′N")
    ax.set_xticks(xt); ax.set_xticklabels(xl, fontsize=7.5, color=INK)
    ax.set_yticks(yt); ax.set_yticklabels(yl, fontsize=7.5, color=INK)
    ax.tick_params(axis="both", direction="out", length=4, width=0.8, pad=3, colors=INK,
                   top=True, bottom=True, left=True, right=True,
                   labeltop=True, labelbottom=True, labelleft=True, labelright=True)
    for t in ax.yaxis.get_major_ticks():
        t.label1.set_rotation(90); t.label1.set_va("center")
        t.label2.set_rotation(270); t.label2.set_va("center")
    ax.grid(True, linestyle=":", linewidth=0.55, color="#94a3b8", alpha=0.65, zorder=8)


def new_sheet(name, block_gdf, title):
    bounds = block_gdf.total_bounds
    bw, bh = bounds[2] - bounds[0], bounds[3] - bounds[1]
    pad_x, pad_y = bw * PAD_FRAC, bh * PAD_FRAC
    xlim = (bounds[0] - pad_x, bounds[2] + pad_x)
    ylim = (bounds[1] - pad_y, bounds[3] + pad_y)
    ar = (xlim[1] - xlim[0]) / (ylim[1] - ylim[0])

    if ar >= 1.0:
        map_w = MAP_MAX_W
        map_h = max(map_w / ar, 4.5)
    else:
        map_h = MAP_MAX_H
        map_w = max(map_h * ar, MAP_MIN_W)

    fw = map_w + M_LEFT + M_RIGHT
    fh = map_h + M_TOP + M_BOTTOM

    fig = plt.figure(figsize=(fw, fh), dpi=300, facecolor="white")
    ax = fig.add_axes([M_LEFT / fw, M_BOTTOM / fh, map_w / fw, map_h / fh])
    ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal", adjustable="box")
    ax.sheet_lim = (xlim, ylim)
    ax.block_name = name

    fig.text(0.5, 1 - 0.30 / fh, title.upper(), fontsize=11.5, ha="center", va="center", color="#374151")
    fig.text(0.5, 1 - 0.68 / fh, name.upper(), fontsize=25, fontweight="bold", ha="center", va="center", color=INK)
    fig.text(0.5, 1 - 0.98 / fh, SUBTITLE, fontsize=9, style="italic", ha="center", va="center", color=GREY)
    fig.text(M_LEFT / fw, 0.13 / fh, "Projection: UTM Zone 43N  |  Datum: WGS 84", fontsize=7, color=GREY, ha="left", va="center")
    return fig, ax, block_gdf.geometry.union_all()


def finish(fig, ax, gdf, geom, out_dir, fname, title, entries, extra=(), bnd=RED, source=""):
    ax.set_xlim(ax.sheet_lim[0]); ax.set_ylim(ax.sheet_lim[1])
    overlay_villages(ax, ax.block_name)
    gdf.boundary.plot(ax=ax, color=bnd, linewidth=1.8, zorder=10)
    ax.set_xlim(ax.sheet_lim[0]); ax.set_ylim(ax.sheet_lim[1])
    dms_ticks(ax)
    entries = [*entries, line("Village boundary", "#475569", 0.8, "--"), dot("Village centre")]
    place_elements(ax, geom, [*extra, legend_el(title, entries), scalebar_el(ax)])
    if source:
        fig.text(1 - M_RIGHT / fig.get_figwidth(), 0.13 / fig.get_figheight(), source, fontsize=7,
                 color=GREY, ha="right", va="center", style="italic")
    out = out_dir / fname
    fig.savefig(out, dpi=300, facecolor="white")
    plt.close(fig)
    print("Saved:", out.name)


# ================================================================= THEMATIC RENDERERS (LOHARA REFERENCE SYMBOLOGY)
def render_study_area(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Study Area & Village Map of")
    hillshade(ax, geom, 0.5)
    finish(fig, ax, gdf, geom, out, f"01_{name}_Study_Area_Map.png", "Legend",
           [line(f"{name} taluka boundary", RED, 2)],
           extra=[location_index_el(name)])


def render_contour_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Contour (10 m) Map of")
    hillshade(ax, geom, 0.45)
    cc = gpd.clip(CONTOURS, gdf)
    cc[cc["is_index"] == 0].plot(ax=ax, color="#854d0e", linewidth=0.4, alpha=0.75, zorder=4)
    idx = cc[cc["is_index"] == 1]
    idx.plot(ax=ax, color="#713f12", linewidth=0.9, alpha=0.95, zorder=5)

    x0, x1 = ax.get_xlim()
    minsep = (x1 - x0) * 0.12
    placed, done = [], set()
    for _, r in idx.assign(L=idx.geometry.length).sort_values("L", ascending=False).iterrows():
        ev = int(r["elev_m"])
        if ev % 50 or ev in done:
            continue
        pt = r.geometry.interpolate(0.5, normalized=True)
        if all(np.hypot(pt.x - a, pt.y - b) > minsep for a, b in placed):
            placed.append((pt.x, pt.y)); done.add(ev)
            ax.text(pt.x, pt.y, f"{ev}", fontsize=7, color="#713f12", ha="center", va="center",
                    path_effects=HALO, zorder=8)

    finish(fig, ax, gdf, geom, out, f"02_{name}_Contour_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            line("Index contour (50 m)", "#713f12", 1.2),
            line("Contour (10 m)", "#854d0e", 0.6)],
           source="Derived from Copernicus GLO-30 DEM (ESA/Airbus)")


def render_lulc_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Land Use / Land Cover Map of")
    hillshade(ax, geom, 0.55, vert_exag=5.0)
    arr, ext = clipped(DATA_PROC / "lulc" / "lulc250k_1617_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    lut = {1: "#dc2626", 2: "#facc15", 3: "#f97316", 4: "#78350f", 5: "#84cc16", 6: "#fef08a",
           7: "#15803d", 9: "#166534", 10: "#4ade80", 14: "#d97706", 16: "#0284c7", 17: "#0369a1"}
    for v, c in lut.items():
        rgba[arr == v] = mcolors.to_rgba(c, 0.62)
    im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    clip_to_geom(im, ax, geom)
    hillshade(ax, geom, 0.28, vert_exag=5.0, zorder=3)
    finish(fig, ax, gdf, geom, out, f"03_{name}_LULC_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Kharif cropland", "#facc15"),
            patch("Double / triple crop", "#84cc16"),
            patch("Current fallow", "#fef08a"),
            patch("Wasteland / scrub", "#d97706"),
            patch("Waterbody", "#0284c7"),
            patch("Settlement", "#dc2626")],
           source="NRSC Bhuvan / ISRO Land Use Land Cover (1:250,000)")


def render_soil_depth_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Soil Depth Classification Map of")
    hillshade(ax, geom, 0.4)
    arr, ext = clipped(DATA_PROC / "soil_depth" / "soildepth_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    rgba[arr == 1] = mcolors.to_rgba("#38bdf8", 0.8)
    rgba[arr == 2] = mcolors.to_rgba("#f59e0b", 0.8)
    rgba[arr == 4] = mcolors.to_rgba("#84cc16", 0.8)
    im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    clip_to_geom(im, ax, geom)
    finish(fig, ax, gdf, geom, out, f"04_{name}_Soil_Depth_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Very shallow (10-25 cm)", "#84cc16"),
            patch("Shallow (25-50 cm)", "#f59e0b"),
            patch("Deep / mod. deep (>50 cm)", "#38bdf8")],
           source="National Bureau of Soil Survey & Land Use Planning (NBSS&LUP)")


def render_road_network_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Classified Road Network Map of")
    hillshade(ax, geom, 0.4)
    rc = gpd.clip(ROADS, gdf)
    colors = {"Trunk/Motorway": "#dc2626", "Primary": "#ea580c", "Secondary": "#d97706",
              "Tertiary": "#0284c7", "Residential/Unclassified": "#64748b", "Track/Path": "#94a3b8"}
    widths = {"Trunk/Motorway": 2.4, "Primary": 2.0, "Secondary": 1.5, "Tertiary": 1.1,
              "Residential/Unclassified": 0.7, "Track/Path": 0.45}
    for k in colors:
        s = rc[rc["road_class"] == k]
        if len(s):
            s.plot(ax=ax, color=colors[k], linewidth=widths[k], zorder=4)
    finish(fig, ax, gdf, geom, out, f"05_{name}_Road_Network_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            line("National highway", "#dc2626", 2.4),
            line("State highway (SH)", "#ea580c", 2.0),
            line("Major district road (MDR)", "#d97706", 1.5),
            line("Other district road (ODR)", "#0284c7", 1.1),
            line("Rural / village road", "#64748b", 0.8)],
           source="OpenStreetMap contributors (ODbL)")


def render_rainfall_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Annual Rainfall & Isohyet Map of")
    hillshade(ax, geom, 0.50, vert_exag=4.0)
    arr, ext = clipped(DATA_PROC / "rainfall" / "rain_mean_mm_1991_2024.tif", geom, buffer=4000)
    arr = arr.astype("float32")
    arr[~np.isfinite(arr) | (arr < 0)] = np.nan
    arr = np.where(np.isnan(arr), np.nanmean(arr), arr)
    sm = scipy.ndimage.gaussian_filter(scipy.ndimage.zoom(arr, 25, order=3), sigma=1.5)
    vmin, vmax = float(np.nanmin(sm)), float(np.nanmax(sm))
    im = ax.imshow(sm, extent=ext, cmap="YlGnBu", vmin=vmin, vmax=vmax, alpha=0.70, zorder=2)
    clip_to_geom(im, ax, geom)

    xg = np.linspace(ext[0], ext[1], sm.shape[1])
    yg = np.linspace(ext[3], ext[2], sm.shape[0])
    step = 20 if (vmax - vmin) > 60 else 10
    levels = np.arange(np.floor(vmin / step) * step, np.ceil(vmax / step) * step + step, step)
    cs = ax.contour(xg, yg, sm, levels=levels, colors="#1e3a8a", linewidths=0.9, zorder=4)
    clip_to_geom(cs, ax, geom)

    clip_patch = mpatches.PathPatch(geom_to_path(geom), transform=ax.transData, fc="none", ec="none")
    ax.add_patch(clip_patch)
    for t in ax.clabel(cs, inline=True, fmt="%d", fontsize=7.5, colors="#0f172a"):
        t.set_path_effects(HALO)
        t.set_clip_path(clip_patch)

    finish(fig, ax, gdf, geom, out, f"06_{name}_Rainfall_Isohyet_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            line(f"Isohyet ({step} mm interval)", "#1e3a8a", 1.0),
            patch("Mean annual rainfall", "#38bdf8")],
           source="Rainfall: CHIRPS 1991-2024 mean climatology")


def render_lithology_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Lithology & Hydrogeology Well Map of")
    hillshade(ax, geom, 0.45)
    gdf.plot(ax=ax, facecolor="#fde68a", alpha=0.4, edgecolor="none", zorder=2)
    if WELLS is not None:
        (x0, x1), (y0, y1) = ax.sheet_lim
        wc = gpd.clip(WELLS, box(x0, y0, x1, y1))
        ax.scatter(wc.geometry.x, wc.geometry.y, s=36, color="#0284c7", edgecolor="white", linewidth=0.9, zorder=6)
        halo_labels(ax, [(w.geometry.x, w.geometry.y + 250,
                          f"{str(w.get('Location', 'Well')).title()} ({w.get('Depth_of_Drill__m_', 'N/A')} m)")
                         for _, w in wc.iterrows()], size=6.5, color="#0f172a")
    finish(fig, ax, gdf, geom, out, f"07_{name}_Lithology_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Deccan Trap basalt", "#fde68a", "#ca8a04"),
            dot("CGWB observation well", "#0284c7")],
           source="CGWB Regional Ground Water Lithologs / GSI (1:250,000)")


def render_dem_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Digital Elevation Model (DEM) of")
    arr, ext = clipped(DATA_PROC / "dem" / "dem_aoi.tif", geom, nodata=-9999)
    dem = arr.astype("float32")
    bad = ~np.isfinite(dem) | (dem < -500)
    vmin, vmax = float(dem[~bad].min()), float(dem[~bad].max())
    dem[bad] = vmin
    cmap = plt.get_cmap("terrain")
    rgb = mcolors.LightSource(azdeg=315, altdeg=45).shade(dem, cmap=cmap, blend_mode="overlay",
                                                         vert_exag=3.5, vmin=vmin, vmax=vmax)
    rgb[bad, 3] = 0
    im = ax.imshow(rgb, extent=ext, zorder=2, interpolation="bilinear")
    clip_to_geom(im, ax, geom)
    finish(fig, ax, gdf, geom, out, f"08_{name}_DEM_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2)],
           extra=[elev_el(round(vmin), round(vmax), cmap)],
           source="Copernicus DEM GLO-30 (ESA / Airbus Defence & Space)")


def render_administrative_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Administrative & Revenue Map of")
    hillshade(ax, geom, 0.3)
    sv = villages(name).copy()
    pal = ["#dbeafe", "#fde68a", "#d1fae5", "#fce7f3", "#e9d5ff", "#fed7aa"]
    sv["_c"] = [pal[i % len(pal)] for i in range(len(sv))]
    sv.plot(ax=ax, color=sv["_c"], alpha=0.55, edgecolor="#475569", linewidth=0.5, zorder=3)
    finish(fig, ax, gdf, geom, out, f"09_{name}_Administrative_Map.png", "Legend",
           [line(f"{name} taluka boundary", INK, 2)], bnd=INK)


def render_slope_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Slope Percentage & Relief Map of")
    hillshade(ax, geom, 0.55, vert_exag=5.0)
    s, ext = clipped(DATA_PROC / "slope" / "slope_deg_pct.tif", geom, nodata=np.nan, band=0)
    s = s.astype("float32")
    rgba = np.zeros((*s.shape, 4), dtype=np.float32)
    for lo, hi, c in ((0, 1, "#dbeafe"), (1, 3, "#93c5fd"), (3, 5, "#fef08a"),
                      (5, 10, "#f59e0b"), (10, np.inf, "#dc2626")):
        rgba[(s >= lo) & (s < hi)] = mcolors.to_rgba(c, 0.6)
    im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    clip_to_geom(im, ax, geom)
    hillshade(ax, geom, 0.28, vert_exag=5.0, zorder=3)
    finish(fig, ax, gdf, geom, out, f"10_{name}_Slope_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("0-1 %  Nearly level", "#dbeafe", "#9ca3af"),
            patch("1-3 %  Very gently sloping", "#93c5fd"),
            patch("3-5 %  Gently sloping", "#fef08a"),
            patch("5-10 %  Moderately sloping", "#f59e0b"),
            patch(">10 %  Strongly sloping", "#dc2626")],
           source="Derived from Copernicus GLO-30 DEM (Horn 1981 algorithm)")


def render_stream_order_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Strahler Stream Order & Drainage Map of")
    hillshade(ax, geom, 0.45, vert_exag=4.0)
    sc = gpd.clip(STREAMS, gdf)
    order_style = {
        1: ("#7dd3fc", 0.6,  "1st order (headwater)"),
        2: ("#38bdf8", 1.0,  "2nd order (tributary)"),
        3: ("#0284c7", 1.8,  "3rd order (major stream)"),
        4: ("#1d4ed8", 2.8,  "4th order (sub-basin river)"),
        5: ("#0f172a", 4.0,  "5th order (main river)"),
    }
    entries = [line(f"{name} boundary", RED, 2)]
    for order in sorted(sc["strahler"].unique()):
        col, lw, lab = order_style.get(order, ("#0f172a", 2.0, f"Order {order}"))
        sc[sc["strahler"] == order].plot(ax=ax, color=col, linewidth=lw, zorder=3 + order)
        entries.append(line(lab, col, lw))
    finish(fig, ax, gdf, geom, out, f"11_{name}_Stream_Order_Map.png", "Legend", entries,
           source="Derived from DEM (WhiteboxTools D8, 3 km² threshold)")


def render_ndvi_seasonal_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Seasonal NDVI & Vegetation Dynamics Map of")
    hillshade(ax, geom, 0.50, vert_exag=4.5)
    ndvi_file = DATA_PROC / "ndvi" / "ndvi_seasonal_aoi.tif"
    if not ndvi_file.exists():
        ndvi_file = DATA_PROC / "ndvi" / "ndvi_kharif_2024_utm.tif"
    arr, ext = clipped(ndvi_file, geom, nodata=-9999)
    arr = arr.astype("float32")
    valid = (arr != -9999) & np.isfinite(arr)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    bins = [
        (-1.0, 0.15, "#fef08a", 0.65),
        (0.15, 0.30, "#bef264", 0.65),
        (0.30, 0.45, "#4ade80", 0.68),
        (0.45, 0.60, "#16a34a", 0.70),
        (0.60, 1.00, "#14532d", 0.75),
    ]
    for lo, hi, col, a in bins:
        m = valid & (arr >= lo) & (arr < hi)
        rgba[m] = mcolors.to_rgba(col, a)
    im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    clip_to_geom(im, ax, geom)
    hillshade(ax, geom, 0.25, vert_exag=4.5, zorder=3)
    finish(fig, ax, gdf, geom, out, f"12_{name}_Seasonal_NDVI_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("> 0.60  Peak vigor / dense canopy", "#14532d"),
            patch("0.45-0.60  Healthy crop canopy", "#16a34a"),
            patch("0.30-0.45  Moderate vegetation", "#4ade80"),
            patch("0.15-0.30  Sparse / emerging crop", "#bef264"),
            patch("< 0.15  Fallow / bare ground", "#fef08a")],
           source="Sentinel-2 L2A (10 m), Cloud Score+ masked (Kharif Season 2024)")


def render_soil_texture_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Soil Texture Classification Map of")
    hillshade(ax, geom, 0.50, vert_exag=4.5)
    arr, ext = clipped(DATA_PROC / "soil_texture" / "soil_texture_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    rgba[arr == 1] = mcolors.to_rgba("#78350f", 0.65)
    rgba[arr == 4] = mcolors.to_rgba("#d97706", 0.65)
    im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    clip_to_geom(im, ax, geom)
    hillshade(ax, geom, 0.28, vert_exag=4.5, zorder=3)
    finish(fig, ax, gdf, geom, out, f"13_{name}_Soil_Texture_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Clay (Deep Black Soil / Vertisol)", "#78350f"),
            patch("Clay Loam (Mod. deep gravelly soil)", "#d97706")],
           source="ISRIC / OpenLandMap USDA Soil Texture System (250 m)")


def render_geomorphology_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Hydrogeomorphology & Terrain Units Map of")
    hillshade(ax, geom, 0.45, vert_exag=4.5)
    p = DATA_PROC / "geomorphology" / "bhuvan_geomorphology_utm.tif"
    if p.exists():
        rgba, ext = clipped_rgba(p, geom)
        im = ax.imshow(rgba, extent=ext, zorder=2, interpolation="bilinear")
        clip_to_geom(im, ax, geom)
    hillshade(ax, geom, 0.25, vert_exag=4.5, zorder=3)
    finish(fig, ax, gdf, geom, out, f"14_{name}_Geomorphology_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Upper Plateau Plain (Basalt)", "#f87171"),
            patch("Dissected Plateau / Escarpments", "#ea580c"),
            patch("Valley Fill / Infiltration Zone", "#854d0e"),
            patch("Surface Water Bodies", "#38bdf8")],
           source="NRSC Bhuvan 1:50,000 Geomorphology (ISRO)")


def render_rgndwm_grid_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "RGNDWM Ground Water Prospects 250k Framework of")
    hillshade(ax, geom, 0.45, vert_exag=3.5)
    gdf.plot(ax=ax, facecolor="#e0e7ff", alpha=0.35, edgecolor="none", zorder=2)

    if SUBBLOCKS is not None:
        v_clip = gpd.clip(SUBBLOCKS, geom)
        v_clip.boundary.plot(ax=ax, color="#cbd5e1", linewidth=0.5, alpha=0.7, zorder=3)

    if STREAMS is not None:
        st_clip = gpd.clip(STREAMS, geom)
        st_hi = st_clip[st_clip["strahler"] >= 3]
        for ord_val, w, col in [(3, 0.7, "#7dd3fc"), (4, 1.2, "#38bdf8"), (5, 1.8, "#0284c7")]:
            sub = st_hi[st_hi["strahler"] == ord_val]
            if not sub.empty:
                sub.plot(ax=ax, color=col, linewidth=w, alpha=0.85, zorder=4)

    if ROADS is not None:
        rd_clip = gpd.clip(ROADS, geom)
        rd_clip.plot(ax=ax, color="#fbbf24", linewidth=0.8, alpha=0.5, zorder=4)

    entries = [line(f"{name} boundary", RED, 2.2),
               line("Village Boundaries", "#94a3b8", 0.6),
               line("Major Streams (Order 3-5)", "#0284c7", 1.5)]

    (x0, x1), (y0, y1) = ax.sheet_lim
    view_box = box(x0, y0, x1, y1)

    quad_defs = [("47N", 75.0, 18.0), ("47O", 75.0, 17.0), ("56B", 76.0, 18.0), ("56C", 76.0, 17.0)]
    subsheet_list = []
    for qname, qx0, qy0 in quad_defs:
        for row in range(4):
            lat_top = qy0 + 1.0 - row * 0.25
            lat_bot = lat_top - 0.25
            for col in range(4):
                lon_left = qx0 + col * 0.25
                lon_right = lon_left + 0.25
                sheet_num = row * 4 + col + 1
                poly = box(lon_left, lat_bot, lon_right, lat_top)
                subsheet_list.append({"code": f"{qname}/{sheet_num}", "geometry": poly})

    gdf_sub = gpd.GeoDataFrame(subsheet_list, crs="EPSG:4326").to_crs(32643)
    gdf_sub_clip = gpd.clip(gdf_sub, view_box)
    gdf_sub_clip.boundary.plot(ax=ax, color="#475569", linewidth=1.1, linestyle="--", alpha=0.85, zorder=6)
    entries.append(line("SOI 15' × 15' Toposheet Grid (50k)", "#475569", 1.1))

    for _, r in gdf_sub_clip.iterrows():
        cx, cy = r.geometry.centroid.x, r.geometry.centroid.y
        if x0 + (x1 - x0) * 0.05 < cx < x1 - (x1 - x0) * 0.05 and y0 + (y1 - y0) * 0.05 < cy < y1 - (y1 - y0) * 0.05:
            ax.text(cx, cy, r["code"], fontsize=10.5, fontweight="bold",
                    color="#1e293b", ha="center", va="center", path_effects=HALO, zorder=8)

    if RGNDWM_GRIDS is not None:
        rg = gpd.clip(RGNDWM_GRIDS, view_box)
        rg.boundary.plot(ax=ax, color="#1e1b4b", linewidth=2.2, linestyle="-", zorder=7)
        entries.append(line("RGNDWM 1° × 1° Sheet Boundary", "#1e1b4b", 2.0))
        for _, r in rg.iterrows():
            sheet_no = str(r["MAP_NO"])
            entries.append(patch(f"SOI Topo Sheet {sheet_no}", "#c7d2fe", "#1e1b4b"))

    finish(fig, ax, gdf, geom, out, f"15_{name}_RGNDWM_250k_Framework_Map.png", "Legend", entries,
           source="National Remote Sensing Centre (NRSC) / RGNDWM (1° x 1° Grid Index)")


def compute_drainage_density_raster(geom, streams_gdf, res=50.0, sigma_m=800.0):
    minx, miny, maxx, maxy = geom.bounds
    pad = 2500.0
    gx0, gy0, gx1, gy1 = minx - pad, miny - pad, maxx + pad, maxy + pad
    nx = int(np.ceil((gx1 - gx0) / res))
    ny = int(np.ceil((gy1 - gy0) / res))
    grid = np.zeros((ny, nx), dtype=np.float32)

    bbox_poly = box(gx0, gy0, gx1, gy1)
    s_sub = gpd.clip(streams_gdf, bbox_poly)

    for _, row in s_sub.iterrows():
        g = row.geometry
        if g is None or g.is_empty:
            continue
        lines = [g] if g.geom_type == "LineString" else list(g.geoms)
        for line_geom in lines:
            coords = np.array(line_geom.coords)
            for i in range(len(coords) - 1):
                p1, p2 = coords[i], coords[i + 1]
                seg_len_km = np.sqrt(np.sum((p2[:2] - p1[:2]) ** 2)) / 1000.0
                n_samples = max(1, int(np.ceil(seg_len_km * 1000.0 / (res / 2.0))))
                sub_len_km = seg_len_km / n_samples
                for t in np.linspace(0.5 / n_samples, 1 - 0.5 / n_samples, n_samples):
                    px = p1[0] + t * (p2[0] - p1[0])
                    py = p1[1] + t * (p2[1] - p1[1])
                    col = int((px - gx0) / res)
                    row_idx = int((gy1 - py) / res)
                    if 0 <= col < nx and 0 <= row_idx < ny:
                        grid[row_idx, col] += sub_len_km

    sigma_cells = sigma_m / res
    smooth_len_km = scipy.ndimage.gaussian_filter(grid, sigma=sigma_cells)
    cell_area_km2 = (res / 1000.0) ** 2
    density_km2 = smooth_len_km / cell_area_km2
    extent = [gx0, gx1, gy0, gy1]
    return density_km2, extent


def render_drainage_density_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Drainage Density (Dd) Continuous Heatmap of")
    hillshade(ax, geom, 0.32)

    density_grid, extent = compute_drainage_density_raster(geom, STREAMS, res=50.0, sigma_m=800.0)

    cmap = plt.cm.YlGnBu
    im = ax.imshow(density_grid, extent=extent, cmap=cmap, vmin=0.0, vmax=3.0,
                   alpha=0.68, zorder=2, interpolation="bicubic")
    clip_to_geom(im, ax, geom)

    nx, ny = density_grid.shape[1], density_grid.shape[0]
    xs = np.linspace(extent[0], extent[1], nx)
    ys = np.linspace(extent[3], extent[2], ny)
    levels = [0.5, 1.0, 1.5, 2.0, 2.5]
    cs = ax.contour(xs, ys, density_grid, levels=levels, colors="#0369a1",
                    linewidths=0.5, alpha=0.55, zorder=3)
    clip_to_geom(cs, ax, geom)

    s_clip = gpd.clip(STREAMS, geom)
    s_clip.plot(ax=ax, color="#1e3a8a", linewidth=0.55, alpha=0.75, zorder=4)

    v = villages(name)
    if v is not None and not v.empty:
        v.boundary.plot(ax=ax, color="#475569", linewidth=0.35, linestyle=":", alpha=0.6, zorder=5)

    entries = [
        line("Stream channel network", "#1e3a8a", 1.0),
        line("Density isopleth (0.5 km/km² int.)", "#0369a1", 0.7, ls="-"),
        line("Village cadastral boundary", "#475569", 0.5, ls=":")
    ]

    extra_elements = [
        density_cbar_el(vmin=0.0, vmax=3.0, cmap="YlGnBu", title="Drainage Density (km / km²)")
    ]

    finish(fig, ax, gdf, geom, out, f"16_{name}_Drainage_Density_Map.png", "Legend", entries,
           extra=extra_elements,
           source="Derived from WhiteboxTools D8 Hydro DEM Network (50m metric KDE, 800m sigma)")


RENDERERS = [
    render_study_area, render_contour_map, render_lulc_map, render_soil_depth_map,
    render_road_network_map, render_rainfall_map, render_lithology_map, render_dem_map,
    render_administrative_map, render_slope_map, render_stream_order_map,
    render_ndvi_seasonal_map, render_soil_texture_map, render_geomorphology_map,
    render_rgndwm_grid_map, render_drainage_density_map
]


THEME_RENDERERS = {
    "study_area": render_study_area,
    "contour": render_contour_map,
    "lulc": render_lulc_map,
    "soil_depth": render_soil_depth_map,
    "road": render_road_network_map,
    "rainfall": render_rainfall_map,
    "lithology": render_lithology_map,
    "dem": render_dem_map,
    "administrative": render_administrative_map,
    "slope": render_slope_map,
    "stream_order": render_stream_order_map,
    "ndvi": render_ndvi_seasonal_map,
    "soil_texture": render_soil_texture_map,
    "geomorphology": render_geomorphology_map,
    "rgndwm": render_rgndwm_grid_map,
    "drainage_density": render_drainage_density_map,
}


def generate_all_block_maps(blocks=("Tuljapur", "Lohara"), themes=None):
    if themes:
        selected_renderers = []
        for t in themes:
            t_clean = str(t).lower().strip().replace(" ", "_")
            # match by key or by prefix / partial match
            matched = False
            for k, v in THEME_RENDERERS.items():
                if t_clean in k or k in t_clean:
                    selected_renderers.append(v)
                    matched = True
                    break
            if not matched:
                print(f"Warning: Unknown theme '{t}', available themes: {list(THEME_RENDERERS.keys())}")
        active_renderers = selected_renderers if selected_renderers else RENDERERS
    else:
        active_renderers = RENDERERS

    for name in blocks:
        print(f"\n>>> Generating Maps for {name} Taluka ({len(active_renderers)} Themes)")
        out = MAPS_DIR / name
        out.mkdir(parents=True, exist_ok=True)
        gdf = AOI_BLOCKS[AOI_BLOCKS["NAME"] == name]
        if gdf is None or gdf.empty:
            print(f"Warning: Block '{name}' not found in AOI_BLOCKS.")
            continue
        for fn in active_renderers:
            fn(name, gdf, out)
    print("\nSUCCESS: Block Maps Saved to:", MAPS_DIR)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Cartographic Map Generation Engine")
    parser.add_argument("blocks", nargs="*", default=["Tuljapur", "Lohara"], help="Target block name(s), e.g. Lohara Tuljapur")
    parser.add_argument("--theme", "--layer", "-t", nargs="+", default=None,
                        help="Specific theme(s) to render, e.g. dem, contour, lulc")
    args = parser.parse_args()
    generate_all_block_maps(blocks=args.blocks, themes=args.theme)


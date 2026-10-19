#!/usr/bin/env python3
"""
Block Map Production Engine v2 - clean production cartography.

Changes vs v1
- Canvas fitted to block aspect ratio: no dead space left/right (landscape) or top/bottom (portrait)
- No double neatline / outer sheet border: single thin map frame + DMS collar only
- Header laid out in fixed inch slots: title / block name / subtitle never collide
- Legend, scale bar, north arrow auto-placed in the emptiest corner (min overlap with block polygon)
- Legend = clean boxed panel with proper swatches; sized from content
- Scale bar = 4-segment alternating bar, auto "nice" length, label "km"
- Hillshade clipped to block (no grey buffer rectangle)
- Village / well labels de-overlapped (adjustText if installed) + white halo
- Rainfall raster & isohyets clipped to block outline

pip install adjustText   (optional but recommended for label de-overlap)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.colors as mcolors
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
import matplotlib.pyplot as plt
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
except ImportError:  # labels still drawn, just not de-overlapped
    adjust_text = None

BASE_DIR = Path(__file__).resolve().parent.parent
MAP_DATA = BASE_DIR / "map_data"
MAPS_DIR = MAP_DATA / "maps"

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

AOI_BLOCKS = _read(MAP_DATA / "aoi" / "aoi_blocks.gpkg")
SUBBLOCKS = _read(MAP_DATA / "aoi" / "subblocks_villages.gpkg")
ROADS = _read(MAP_DATA / "roads" / "roads_osm.gpkg")
WELLS = _read(MAP_DATA / "lithology" / "cgwb_litholog_regional_wells_50km.gpkg")
CONTOURS = _read(MAP_DATA / "dem" / "contours_10m.gpkg")
STREAMS = _read(MAP_DATA / "streams" / "streams_complete_strahler.gpkg")
RGNDWM_GRIDS = _read(BASE_DIR / "data" / "India 250k Polygon.geojson")

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
    except AttributeError:  # old matplotlib ContourSet
        for c in artist.collections:
            c.set_clip_path(patch)


def clipped(path, geom, nodata=None, band=0, buffer=0):
    with rasterio.open(path) as src:
        g = geom.buffer(buffer) if buffer else geom
        kw = {} if nodata is None else {"nodata": nodata}
        out, tr = mask(src, [g], crop=True, **kw)
    arr = out[band]
    ext = [tr.c, tr.c + tr.a * arr.shape[1], tr.f + tr.e * arr.shape[0], tr.f]
    return arr, ext


def clipped_rgba(path, geom):
    with rasterio.open(path) as src:
        out, tr = mask(src, [geom], crop=True)
    arr = out.transpose(1, 2, 0)
    ext = [tr.c, tr.c + tr.a * arr.shape[1], tr.f + tr.e * arr.shape[0], tr.f]
    return arr, ext


def hillshade(ax, geom, alpha=0.5, vert_exag=3.5, zorder=1):
    p = MAP_DATA / "dem" / "dem_aoi.tif"
    if not p.exists():
        return
    arr, ext = clipped(p, geom, nodata=-9999)
    dem = arr.astype("float32")
    bad = ~np.isfinite(dem) | (dem < -500)
    dem[bad] = np.nanmin(dem[~bad])
    hs = mcolors.LightSource(azdeg=315, altdeg=45).hillshade(dem, vert_exag=vert_exag)
    rgba = plt.cm.gray(0.25 + 0.75 * hs)
    rgba[..., 3] = np.where(bad, 0.0, alpha)
    ax.imshow(rgba, extent=ext, zorder=zorder, interpolation="bilinear")


def villages(name):
    return SUBBLOCKS[SUBBLOCKS["BLOCK"] == name]


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


def village_labels(ax, sv):
    pts = sv.geometry.representative_point()
    ax.scatter(pts.x, pts.y, s=8, color=DOT, edgecolor="white", linewidth=0.5, zorder=11)
    halo_labels(ax, [(p.x, p.y + 150, str(v).strip().title()) for p, v in zip(pts, sv["VILLAGE"])])


def overlay_villages(ax, name):
    """Village boundaries + dots + de-overlapped labels; drawn on every map."""
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


# ---------------------------------------------------------------- map furniture (all drawn in inch units)
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
    mpi = (x1 - x0) / aw                       # metres per inch
    target = 2.4 * mpi
    km = max([k for k in (2, 4, 8, 10, 12, 20, 40, 80) if k * 1000 <= target] or [2])
    bar = km * 1000 / mpi
    ox = 0.12
    w, h = ox + bar + 0.45, 0.42

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        seg = bar / 4
        for i in range(4):
            ia.add_patch(mpatches.Rectangle((ox + i * seg, 0.10), seg, 0.08,
                                            fc="black" if i % 2 == 0 else "white", ec="black", lw=0.7))
        for frac, lab in ((0, "0"), (0.5, f"{km // 2}"), (1, f"{km} km")):
            ia.text(ox + frac * bar, 0.24, lab, fontsize=7.5, ha="center", va="bottom", color=INK,
                    path_effects=HALO)
    return w, h, draw


def north_el():
    w, h = 0.55, 0.95

    def draw(ia, w, h):
        ia.patch.set_alpha(0.0)
        ia.patch.set_facecolor("none")
        c = w / 2
        ia.add_patch(mpatches.Polygon([(c, 0.68), (c - 0.12, 0.08), (c, 0.22)], fc="black", ec="black", lw=0.7))
        ia.add_patch(mpatches.Polygon([(c, 0.68), (c + 0.12, 0.08), (c, 0.22)], fc="white", ec="black", lw=0.7))
        ia.text(c, 0.72, "N", fontsize=12, fontweight="bold", ha="center", va="bottom", color=INK, path_effects=HALO)
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


def place_elements(ax, geom, elements):
    """Put each element in the free corner with least overlap with the block polygon."""
    fig, pos = ax.figure, ax.get_position()
    aw, ah = pos.width * fig.get_figwidth(), pos.height * fig.get_figheight()
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    sx, sy = (x1 - x0) / aw, (y1 - y0) / ah
    m, pad = 0.12, 0.10
    free = ["ll", "lr", "ul", "ur"]            # [vertical l/u][horizontal l/r]
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


# ---------------------------------------------------------------- sheet
def dms_ticks(ax):
    (x0, x1), (y0, y1) = ax.get_xlim(), ax.get_ylim()
    cs = [TO_WGS.transform(x, y) for x in (x0, x1) for y in (y0, y1)]
    lons, lats = [c[0] for c in cs], [c[1] for c in cs]
    lo0, lo1, la0, la1 = min(lons), max(lons), min(lats), max(lats)
    span = max(lo1 - lo0, la1 - la0) * 60
    step = next((s for s in (1, 2, 5, 10, 15, 30) if span / s <= 6), 30)
    xt, xl, yt, yl = [], [], [], []
    for m in range(int(np.ceil(lo0 * 60 / step)) * step, int(np.floor(lo1 * 60 / step)) * step + 1, step):
        x = TO_UTM.transform(m / 60, (la0 + la1) / 2)[0]
        if x0 <= x <= x1:
            xt.append(x); xl.append(f"{m // 60}°{m % 60:02d}′E")
    for m in range(int(np.ceil(la0 * 60 / step)) * step, int(np.floor(la1 * 60 / step)) * step + 1, step):
        y = TO_UTM.transform((lo0 + lo1) / 2, m / 60)[1]
        if y0 <= y <= y1:
            yt.append(y); yl.append(f"{m // 60}°{m % 60:02d}′N")
    ax.set_xticks(xt); ax.set_xticklabels(xl)
    ax.set_yticks(yt); ax.set_yticklabels(yl)
    ax.tick_params(axis="both", direction="out", length=4, width=0.7, labelsize=8, pad=3,
                   top=True, bottom=True, left=True, right=True,
                   labeltop=True, labelbottom=True, labelleft=True, labelright=True)
    for t in ax.yaxis.get_major_ticks():
        t.label1.set_rotation(90); t.label1.set_va("center")
        t.label2.set_rotation(270); t.label2.set_va("center")
    ax.grid(color="#9ca3af", lw=0.3, ls=(0, (2, 3)), alpha=0.6)
    ax.set_axisbelow(True)


def new_sheet(name, block_gdf, title):
    minx, miny, maxx, maxy = block_gdf.total_bounds
    px, py = (maxx - minx) * PAD_FRAC, (maxy - miny) * PAD_FRAC
    xlim, ylim = (minx - px, maxx + px), (miny - py, maxy + py)
    aspect = (ylim[1] - ylim[0]) / (xlim[1] - xlim[0])
    map_w = float(np.clip(MAP_MAX_H / aspect, MAP_MIN_W, MAP_MAX_W))
    map_h = map_w * aspect
    fw, fh = map_w + M_LEFT + M_RIGHT, map_h + M_TOP + M_BOTTOM

    fig = plt.figure(figsize=(fw, fh), dpi=300, facecolor="white")
    ax = fig.add_axes([M_LEFT / fw, M_BOTTOM / fh, map_w / fw, map_h / fh])
    ax.set_xlim(xlim); ax.set_ylim(ylim); ax.set_aspect("equal", adjustable="box")
    ax.sheet_lim = (xlim, ylim)
    ax.block_name = name

    # header: fixed inch slots, cannot overlap
    fig.text(0.5, 1 - 0.30 / fh, title.upper(), fontsize=11.5, ha="center", va="center", color="#374151")
    fig.text(0.5, 1 - 0.68 / fh, name.upper(), fontsize=25, fontweight="bold", ha="center", va="center", color=INK)
    fig.text(0.5, 1 - 0.98 / fh, SUBTITLE, fontsize=9, style="italic", ha="center", va="center", color=GREY)
    # footer
    fig.text(M_LEFT / fw, 0.13 / fh, "Projection: UTM Zone 43N  |  Datum: WGS 84", fontsize=7, color=GREY, ha="left", va="center")
    return fig, ax, block_gdf.geometry.union_all()


def finish(fig, ax, gdf, geom, out_dir, fname, title, entries, extra=(), bnd=RED, source=""):
    ax.set_xlim(ax.sheet_lim[0]); ax.set_ylim(ax.sheet_lim[1])
    overlay_villages(ax, ax.block_name)
    gdf.boundary.plot(ax=ax, color=bnd, linewidth=1.8, zorder=10)
    ax.set_xlim(ax.sheet_lim[0]); ax.set_ylim(ax.sheet_lim[1])
    dms_ticks(ax)
    entries = [*entries, line("Village boundary", "#475569", 0.8, "--"), dot("Village centre")]
    place_elements(ax, geom, [legend_el(title, entries), *extra, scalebar_el(ax), north_el()])
    if source:
        fig.text(1 - M_RIGHT / fig.get_figwidth(), 0.13 / fig.get_figheight(), source, fontsize=7,
                 color=GREY, ha="right", va="center", style="italic")
    out = out_dir / fname
    fig.savefig(out, dpi=300, facecolor="white")
    plt.close(fig)
    print("Saved:", out.name)


# ================================================================= THEMES
def render_study_area(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Study Area & Village Map of")
    hillshade(ax, geom, 0.5)
    finish(fig, ax, gdf, geom, out, f"01_{name}_Study_Area_Map.png", "Legend",
           [line(f"{name} taluka boundary", RED, 2)])


def render_contour_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Contour (10 m) Map of")
    hillshade(ax, geom, 0.45)
    cc = gpd.clip(CONTOURS, gdf)
    cc[cc["is_index"] == 0].plot(ax=ax, color="#854d0e", linewidth=0.4, alpha=0.75, zorder=4)
    idx = cc[cc["is_index"] == 1]
    idx.plot(ax=ax, color="#713f12", linewidth=0.9, alpha=0.95, zorder=5)

    # label index contours: longest line per elevation, min separation between labels
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
           [line(f"{name} boundary", RED, 2), line("Index contour (50 m)", "#713f12", 1.2),
            line("Contour (10 m)", "#854d0e", 0.6)])


def render_lulc_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Land Use / Land Cover Map of")
    hillshade(ax, geom, 0.55, vert_exag=5.0)
    arr, ext = clipped(MAP_DATA / "lulc" / "lulc250k_1617_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    lut = {1: "#dc2626", 2: "#facc15", 3: "#f97316", 4: "#78350f", 5: "#84cc16", 6: "#fef08a",
           7: "#15803d", 9: "#166534", 10: "#4ade80", 14: "#d97706", 16: "#0284c7", 17: "#0369a1"}
    for v, c in lut.items():
        rgba[arr == v] = mcolors.to_rgba(c, 0.62)
    ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    # terrain relief overlay on top of thematic colours so terrain pops
    hillshade(ax, geom, 0.28, vert_exag=5.0, zorder=3)
    finish(fig, ax, gdf, geom, out, f"03_{name}_LULC_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2), patch("Kharif cropland", "#facc15"),
            patch("Double / triple crop", "#84cc16"), patch("Current fallow", "#fef08a"),
            patch("Wasteland / scrub", "#d97706"), patch("Waterbody", "#0284c7"),
            patch("Settlement", "#dc2626")])


def render_soil_depth_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Soil Depth Classification Map of")
    hillshade(ax, geom, 0.4)
    arr, ext = clipped(MAP_DATA / "soil_depth" / "soildepth_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    rgba[arr == 1] = mcolors.to_rgba("#38bdf8", 0.8)
    rgba[arr == 2] = mcolors.to_rgba("#f59e0b", 0.8)
    rgba[arr == 4] = mcolors.to_rgba("#84cc16", 0.8)
    ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    finish(fig, ax, gdf, geom, out, f"04_{name}_Soil_Depth_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2), patch("Very shallow (10-25 cm)", "#84cc16"),
            patch("Shallow (25-50 cm)", "#f59e0b"), patch("Deep / mod. deep (>50 cm)", "#38bdf8")])


def render_road_network_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Classified Road Network Map of")
    hillshade(ax, geom, 0.4)
    rc = gpd.clip(ROADS, gdf)
    colors = {"Trunk/Motorway": "#dc2626", "Primary": "#ea580c", "Secondary": "#d97706",
              "Tertiary": "#0284c7", "Residential/Unclassified": "#64748b", "Track/Path": "#94a3b8"}
    widths = {"Trunk/Motorway": 2.4, "Primary": 2.0, "Secondary": 1.5, "Tertiary": 1.1,
              "Residential/Unclassified": 0.7, "Track/Path": 0.45}
    for k in colors:  # dict order = draw order, minor first
        s = rc[rc["road_class"] == k]
        if len(s):
            s.plot(ax=ax, color=colors[k], linewidth=widths[k], zorder=4)
    finish(fig, ax, gdf, geom, out, f"05_{name}_Road_Network_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2), line("National highway", "#dc2626", 2.4),
            line("State highway (SH)", "#ea580c", 2.0), line("Major district road (MDR)", "#d97706", 1.5),
            line("Other district road (ODR)", "#0284c7", 1.1), line("Rural / village road", "#64748b", 0.8)])


def render_rainfall_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Annual Rainfall & Isohyet Map of")
    hillshade(ax, geom, 0.50, vert_exag=4.0)
    # buffer used only for smooth interpolation; everything clipped to block
    arr, ext = clipped(MAP_DATA / "rainfall" / "rain_mean_mm_1991_2024.tif", geom, buffer=4000)
    arr = arr.astype("float32")
    arr[~np.isfinite(arr) | (arr < 0)] = np.nan
    arr = np.where(np.isnan(arr), np.nanmean(arr), arr)
    sm = scipy.ndimage.gaussian_filter(scipy.ndimage.zoom(arr, 25, order=3), sigma=1.5)
    vmin, vmax = float(np.nanmin(sm)), float(np.nanmax(sm))
    # rainfall colour wash — clipped to block
    im = ax.imshow(sm, extent=ext, cmap="YlGnBu", vmin=vmin, vmax=vmax, alpha=0.70, zorder=2)
    clip_to_geom(im, ax, geom)
    # isohyets — clipped to block
    xg = np.linspace(ext[0], ext[1], sm.shape[1])
    yg = np.linspace(ext[3], ext[2], sm.shape[0])
    step = 20 if (vmax - vmin) > 60 else 10
    levels = np.arange(np.floor(vmin / step) * step, np.ceil(vmax / step) * step + step, step)
    cs = ax.contour(xg, yg, sm, levels=levels, colors="#1e3a8a", linewidths=0.9, zorder=4)
    clip_to_geom(cs, ax, geom)
    # contour labels — clip each to block so nothing leaks outside
    clip_patch = mpatches.PathPatch(geom_to_path(geom), transform=ax.transData, fc="none", ec="none")
    ax.add_patch(clip_patch)
    for t in ax.clabel(cs, inline=True, fmt="%d", fontsize=7.5, colors="#0f172a"):
        t.set_path_effects(HALO)
        t.set_clip_path(clip_patch)
    finish(fig, ax, gdf, geom, out, f"06_{name}_Rainfall_Isohyet_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2), line(f"Isohyet ({step} mm interval)", "#1e3a8a", 1.0),
            patch("Mean annual rainfall", "#38bdf8")],
           source="Rainfall: CHIRPS 1991-2024 mean")


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
           [line(f"{name} boundary", RED, 2), patch("Deccan Trap basalt", "#fde68a", "#ca8a04"),
            dot("CGWB observation well", "#0284c7")])


def render_dem_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Digital Elevation Model (DEM) of")
    arr, ext = clipped(MAP_DATA / "dem" / "dem_aoi.tif", geom, nodata=-9999)
    dem = arr.astype("float32")
    bad = ~np.isfinite(dem) | (dem < -500)
    vmin, vmax = float(dem[~bad].min()), float(dem[~bad].max())
    dem[bad] = vmin
    cmap = plt.get_cmap("terrain")
    rgb = mcolors.LightSource(azdeg=315, altdeg=45).shade(dem, cmap=cmap, blend_mode="overlay",
                                                         vert_exag=3.5, vmin=vmin, vmax=vmax)
    rgb[bad, 3] = 0
    ax.imshow(rgb, extent=ext, zorder=2, interpolation="bilinear")
    finish(fig, ax, gdf, geom, out, f"08_{name}_DEM_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2)], extra=[elev_el(round(vmin), round(vmax), cmap)])


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
    s, ext = clipped(MAP_DATA / "slope" / "slope_deg_pct.tif", geom, nodata=np.nan, band=1)
    s = s.astype("float32")
    rgba = np.zeros((*s.shape, 4), dtype=np.float32)
    for lo, hi, c in ((0, 1, "#dbeafe"), (1, 3, "#93c5fd"), (3, 5, "#fef08a"),
                      (5, 10, "#f59e0b"), (10, np.inf, "#dc2626")):
        rgba[(s >= lo) & (s < hi)] = mcolors.to_rgba(c, 0.6)
    ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    # terrain relief overlay on top of thematic colours so terrain pops
    hillshade(ax, geom, 0.28, vert_exag=5.0, zorder=3)
    finish(fig, ax, gdf, geom, out, f"10_{name}_Slope_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2), patch("0-1 %  Nearly level", "#dbeafe", "#9ca3af"),
            patch("1-3 %  Very gently sloping", "#93c5fd"), patch("3-5 %  Gently sloping", "#fef08a"),
            patch("5-10 %  Moderately sloping", "#f59e0b"), patch(">10 %  Strongly sloping", "#dc2626")])


def render_stream_order_map(name, gdf, out):
    """11. Strahler Stream Order & Drainage Network Map."""
    if STREAMS is None:
        print("  Skipped: streams data not found")
        return
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
    arr, ext = clipped(MAP_DATA / "ndvi" / "ndvi_kharif_2024_utm.tif", geom, nodata=-9999)
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
    ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
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
    arr, ext = clipped(MAP_DATA / "soil_texture" / "soil_texture_aoi_utm.tif", geom, nodata=255)
    rgba = np.zeros((*arr.shape, 4), dtype=np.float32)
    rgba[arr == 1] = mcolors.to_rgba("#78350f", 0.65)
    rgba[arr == 4] = mcolors.to_rgba("#d97706", 0.65)
    ax.imshow(rgba, extent=ext, zorder=2, interpolation="nearest")
    hillshade(ax, geom, 0.28, vert_exag=4.5, zorder=3)
    finish(fig, ax, gdf, geom, out, f"13_{name}_Soil_Texture_Map.png", "Legend",
           [line(f"{name} boundary", RED, 2),
            patch("Clay (Deep Black Soil / Vertisol)", "#78350f"),
            patch("Clay Loam (Mod. deep gravelly soil)", "#d97706")],
           source="ISRIC / OpenLandMap USDA Soil Texture System (250 m)")


def render_geomorphology_map(name, gdf, out):
    fig, ax, geom = new_sheet(name, gdf, "Hydrogeomorphology & Terrain Units Map of")
    hillshade(ax, geom, 0.45, vert_exag=4.5)
    p = MAP_DATA / "geomorphology" / "bhuvan_geomorphology_utm.tif"
    if p.exists():
        rgba, ext = clipped_rgba(p, geom)
        ax.imshow(rgba, extent=ext, zorder=2, interpolation="bilinear")
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

    # Village boundaries
    if SUBBLOCKS is not None:
        v_clip = gpd.clip(SUBBLOCKS, geom)
        v_clip.boundary.plot(ax=ax, color="#cbd5e1", linewidth=0.5, alpha=0.7, zorder=3)

    # Drainage
    if STREAMS is not None:
        st_clip = gpd.clip(STREAMS, geom)
        st_hi = st_clip[st_clip["strahler"] >= 3]
        for ord_val, w, col in [(3, 0.7, "#7dd3fc"), (4, 1.2, "#38bdf8"), (5, 1.8, "#0284c7")]:
            sub = st_hi[st_hi["strahler"] == ord_val]
            if not sub.empty:
                sub.plot(ax=ax, color=col, linewidth=w, alpha=0.85, zorder=4)

    # Roads
    if ROADS is not None:
        rd_clip = gpd.clip(ROADS, geom)
        rd_clip.plot(ax=ax, color="#fbbf24", linewidth=0.8, alpha=0.5, zorder=4)

    entries = [line(f"{name} boundary", RED, 2.2),
               line("Village Boundaries", "#94a3b8", 0.6),
               line("Major Streams (Order 3-5)", "#0284c7", 1.5)]

    # 1:50k Toposheet grid subdivision (15' x 15')
    (x0, x1), (y0, y1) = ax.sheet_lim
    view_box = box(x0, y0, x1, y1)

    lon0, lat0 = TO_WGS.transform(x0, y0)
    lon1, lat1 = TO_WGS.transform(x1, y1)

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


RENDERERS = [render_study_area, render_contour_map, render_lulc_map, render_soil_depth_map,
             render_road_network_map, render_rainfall_map, render_lithology_map, render_dem_map,
             render_administrative_map, render_slope_map, render_stream_order_map,
             render_ndvi_seasonal_map, render_soil_texture_map, render_geomorphology_map,
             render_rgndwm_grid_map]


def generate_all_block_maps(blocks=("Tuljapur", "Lohara")):
    for name in blocks:
        print(f"\n>>> {name}")
        out = MAPS_DIR / name
        out.mkdir(parents=True, exist_ok=True)
        gdf = AOI_BLOCKS[AOI_BLOCKS["NAME"] == name]
        for fn in RENDERERS:
            fn(name, gdf, out)
    print("\nDone ->", MAPS_DIR)


if __name__ == "__main__":
    generate_all_block_maps()

# ============================================================
#   BIODIVERSITY PARK — PROFESSIONAL LAYOUT PLAN  v3 (FULL)
#   Run entirely in Google Colab — no patching needed
#   Upload KML files when the dialog appears
# ============================================================

# ── STEP 1: Install all dependencies ─────────────────────────
import subprocess, sys

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", pkg])

for pkg in ["shapely", "lxml", "matplotlib", "numpy", "scipy",
            "contextily", "pyproj", "mercantile", "Pillow", "certifi",
            "requests"]:
    install(pkg)

print("✅ All packages installed.")


# ── STEP 2: Imports ───────────────────────────────────────────
import os, io, ssl, warnings
import xml.etree.ElementTree as ET

import numpy as np
import certifi
import requests
import mercantile

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.patheffects as pe
from matplotlib.patches import (FancyBboxPatch, PathPatch, Circle,
                                  Ellipse, FancyArrowPatch)
from matplotlib.path   import Path
from matplotlib.lines  import Line2D
from matplotlib.colors import to_rgba
import matplotlib.ticker as ticker

from shapely.geometry import (Polygon, LineString, Point,
                               MultiPolygon, MultiLineString,
                               GeometryCollection)
from shapely.ops import unary_union, transform as shp_transform
from scipy.ndimage import gaussian_filter

import contextily as ctx
from pyproj import Transformer
from PIL import Image as PILImage

warnings.filterwarnings("ignore")

# Fix SSL in Colab
os.environ["SSL_CERT_FILE"]       = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"]  = certifi.where()
ssl._create_default_https_context = ssl._create_unverified_context

print("✅ Imports done.")


# ── STEP 3: Upload KML files ──────────────────────────────────
try:
    from google.colab import files as colab_files
    IN_COLAB = True
except ImportError:
    IN_COLAB = False

KML_FILES = {}

if IN_COLAB:
    print("\n📂 Please upload ALL your KML files now...")
    uploaded = colab_files.upload()
    for fname, data in uploaded.items():
        with open(fname, "wb") as f:
            f.write(data)
        KML_FILES[fname] = fname
    print(f"✅ {len(KML_FILES)} files uploaded: {list(KML_FILES.keys())}")
else:
    KML_DIR = "."
    for fn in os.listdir(KML_DIR):
        if fn.lower().endswith(".kml"):
            KML_FILES[fn] = os.path.join(KML_DIR, fn)
    print(f"✅ Found {len(KML_FILES)} KML files locally.")


# ── STEP 4: KML Parser ───────────────────────────────────────
def detect_ns(root):
    tag = root.tag
    return tag[1:tag.index("}")] if "{" in tag else ""

def parse_coord_string(text):
    coords = []
    for token in (text or "").strip().split():
        parts = token.split(",")
        if len(parts) >= 2:
            try:
                coords.append((float(parts[0]), float(parts[1])))
            except ValueError:
                pass
    return coords

def safe_polygon(coords):
    if len(coords) < 3:
        return None
    try:
        p = Polygon(coords)
        if not p.is_valid:
            p = p.buffer(0)
        return p if not p.is_empty else None
    except Exception:
        return None

def parse_kml_file(path):
    try:
        tree = ET.parse(path)
    except ET.ParseError as e:
        print(f"  ⚠ XML parse error in {path}: {e}")
        return []
    root = tree.getroot()
    ns   = detect_ns(root)
    tag  = lambda t: f"{{{ns}}}{t}" if ns else t
    results = []

    for pm in root.iter(tag("Placemark")):
        name_el = pm.find(tag("name"))
        name    = (name_el.text or "Feature").strip() if name_el is not None else "Feature"

        for poly_el in pm.iter(tag("Polygon")):
            outer = poly_el.find(f".//{tag('outerBoundaryIs')}//{tag('coordinates')}")
            if outer is None:
                continue
            outer_coords = parse_coord_string(outer.text or "")
            outer_poly   = safe_polygon(outer_coords)
            if outer_poly is None:
                continue
            holes = []
            for inner in poly_el.findall(
                    f".//{tag('innerBoundaryIs')}/{tag('LinearRing')}/{tag('coordinates')}"):
                ic = parse_coord_string(inner.text or "")
                if len(ic) >= 3:
                    holes.append(ic)
            if holes:
                try:
                    outer_poly = Polygon(outer_coords, holes)
                    if not outer_poly.is_valid:
                        outer_poly = outer_poly.buffer(0)
                except Exception:
                    pass
            results.append({"name": name, "geom_type": "Polygon",
                             "geometry": outer_poly})

        for ls_el in pm.iter(tag("LineString")):
            c_el = ls_el.find(tag("coordinates"))
            if c_el is None:
                continue
            coords = parse_coord_string(c_el.text or "")
            if len(coords) >= 2:
                results.append({"name": name, "geom_type": "LineString",
                                 "geometry": LineString(coords)})

        for pt_el in pm.iter(tag("Point")):
            c_el = pt_el.find(tag("coordinates"))
            if c_el is None:
                continue
            coords = parse_coord_string(c_el.text or "")
            if coords:
                results.append({"name": name, "geom_type": "Point",
                                 "geometry": Point(coords[0])})
    return results


# ── STEP 5: Layer assignment ──────────────────────────────────
LAYER_RULES = {
    "plantation on cct": "plantation_cct",
    "plantation"       : "plantation",
    "farm pond"        : "farm_pond",
    "jalkund"          : "jalkund",
    "park road"        : "road",
    "cnb"              : "cnb",
}

def detect_layer(filename):
    fn = filename.lower().replace("_", " ").replace("-", " ")
    for kw, layer in LAYER_RULES.items():
        if kw in fn:
            return layer
    return "other"

LAYER_LABELS = {
    "plantation"    : "Plantation",
    "plantation_cct": "Plantation on CCT",
    "farm_pond"     : "Farm Pond",
    "jalkund"       : "Jalkund",
    "cnb"           : "CNB (Nala Bund)",
    "road"          : "Park Road",
    "other"         : "Other Feature",
}


# ── STEP 6: Load KML files ────────────────────────────────────
layers = {k: [] for k in LAYER_LABELS}

for fname, fpath in KML_FILES.items():
    lk       = detect_layer(fname)
    features = parse_kml_file(fpath)
    print(f"  📄 {fname:42s} → {lk:16s} | {len(features)} features")
    layers[lk].extend(features)

total = sum(len(v) for v in layers.values())
print(f"\n✅ Total features loaded: {total}")


# ── STEP 7: Reproject WGS84 → EPSG:3857 (metres) ─────────────
_T_FWD = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True)
_T_INV = Transformer.from_crs("EPSG:3857", "EPSG:4326", always_xy=True)

def reproject_geom(geom):
    if geom is None or geom.is_empty:
        return geom
    try:
        return shp_transform(_T_FWD.transform, geom)
    except Exception as e:
        print(f"  ⚠ reproject error: {e}")
        return geom

print("\n🔄 Reprojecting all features to EPSG:3857 …")
for lk in layers:
    for feat in layers[lk]:
        feat["geometry"] = reproject_geom(feat["geometry"])
print("✅ Reprojection complete.")


# ── STEP 8: Bounding box ──────────────────────────────────────
all_geoms = [f["geometry"] for feats in layers.values()
             for f in feats if f.get("geometry") and not f["geometry"].is_empty]

if not all_geoms:
    raise ValueError("❌ No valid geometries found. Check your KML files.")

combined = unary_union(all_geoms)
minx, miny, maxx, maxy = combined.bounds
margin = max(maxx - minx, maxy - miny) * 0.10

print(f"🗺  Bounding box (m): X [{minx:.0f}, {maxx:.0f}]  "
      f"Y [{miny:.0f}, {maxy:.0f}]")
print(f"   Area ≈ {(maxx-minx)/1000:.2f} km × {(maxy-miny)/1000:.2f} km")


# ── STEP 9: Low-level draw helpers ───────────────────────────

def _get_polygons(geom):
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    if geom.geom_type == "MultiPolygon":
        return list(geom.geoms)
    if geom.geom_type == "GeometryCollection":
        out = []
        for g in geom.geoms:
            out.extend(_get_polygons(g))
        return out
    return []

def _fill_polygon(ax, geom, facecolor, edgecolor=None,
                   alpha=1.0, lw=0.8, zorder=5,
                   hatch=None, linestyle="-"):
    for p in _get_polygons(geom):
        if p.is_empty:
            continue
        try:
            xs, ys = p.exterior.xy
            ax.fill(xs, ys,
                    facecolor=facecolor,
                    edgecolor=edgecolor or facecolor,
                    alpha=alpha, linewidth=lw, zorder=zorder,
                    hatch=hatch, linestyle=linestyle)
            for hole in p.interiors:
                hx, hy = hole.xy
                ax.fill(hx, hy, facecolor="white",
                        edgecolor=edgecolor or facecolor,
                        linewidth=lw * 0.6, zorder=zorder)
        except Exception:
            pass

def _draw_outline(ax, geom, edgecolor, lw=1.0,
                   alpha=1.0, zorder=6, linestyle="-"):
    polys = _get_polygons(geom)
    if not polys:
        # LineString
        lines = []
        if geom.geom_type == "LineString":
            lines = [geom]
        elif geom.geom_type == "MultiLineString":
            lines = list(geom.geoms)
        for ls in lines:
            xs, ys = ls.xy
            ax.plot(xs, ys, color=edgecolor, lw=lw, alpha=alpha,
                    zorder=zorder, linestyle=linestyle,
                    solid_capstyle="round", solid_joinstyle="round")
        return
    for p in polys:
        if p.is_empty:
            continue
        xs, ys = p.exterior.xy
        ax.plot(xs, ys, color=edgecolor, lw=lw, alpha=alpha,
                zorder=zorder, linestyle=linestyle,
                solid_capstyle="round", solid_joinstyle="round")


# ── STEP 10: Tree symbols (organic AutoCAD plan-view) ─────────

TREE_SPECIES = {
    #              fill        edge        trunk     lobes
    "broadleaf": ("#66BB6A", "#1B5E20", "#3E2723",   8),
    "dry"      : ("#AED581", "#558B2F", "#33691E",   6),
    "flowering": ("#F48FB1", "#880E4F", "#4A148C",   7),
    "fruiting" : ("#FFF176", "#F57F17", "#BF360C",   6),
    "native"   : ("#80DEEA", "#006064", "#004D40",   9),
}

def _organic_path(cx, cy, r, n_lobes, rng):
    n   = n_lobes * 4
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    rad = np.array([
        r * (1.0 + 0.28 * np.sin(i * np.pi / 2) + rng.uniform(-0.12, 0.12))
        for i in range(n)
    ])
    xs = cx + rad * np.cos(ang)
    ys = cy + rad * np.sin(ang)
    verts = [(xs[0], ys[0])]
    codes = [Path.MOVETO]
    for i in range(1, n):
        verts.append((xs[i], ys[i]))
        codes.append(Path.CURVE3)
    verts.append((xs[0], ys[0]))
    codes.append(Path.CLOSEPOLY)
    return Path(verts, codes)

def draw_tree(ax, cx, cy, radius, species="broadleaf",
              zorder=20, rng=None):
    if rng is None:
        rng = np.random.default_rng(int(abs(cx * 1000 + cy)) % 2**31)
    fc, ec, tc, n_lobes = TREE_SPECIES.get(species, TREE_SPECIES["broadleaf"])

    # Shadow
    ax.add_patch(Ellipse((cx + radius * 0.22, cy - radius * 0.18),
                          radius * 2.1, radius * 1.5,
                          facecolor="#00000020", zorder=zorder - 1))
    # Outer canopy
    ax.add_patch(PathPatch(_organic_path(cx, cy, radius, n_lobes, rng),
                            facecolor=fc, edgecolor=ec,
                            linewidth=0.55, alpha=0.90, zorder=zorder))
    # Inner crown mass
    ax.add_patch(PathPatch(_organic_path(cx, cy, radius * 0.52,
                                          max(4, n_lobes - 2), rng),
                            facecolor=ec, edgecolor="none",
                            alpha=0.32, zorder=zorder + 1))
    # Branch lines
    for i in range(n_lobes * 2):
        ang   = 2 * np.pi * i / (n_lobes * 2) + rng.uniform(-0.15, 0.15)
        r_out = radius * rng.uniform(0.55, 0.88)
        ax.plot([cx + radius * 0.08 * np.cos(ang),
                 cx + r_out * np.cos(ang)],
                [cy + radius * 0.08 * np.sin(ang),
                 cy + r_out * np.sin(ang)],
                color=tc, lw=0.30, alpha=0.60,
                zorder=zorder + 2, solid_capstyle="round")
    # Trunk
    ax.plot(cx, cy, "o", color=tc,
            markersize=max(1.4, radius * 0.20),
            markeredgewidth=0, zorder=zorder + 3)
    # Gleam
    ax.add_patch(Ellipse((cx - radius * 0.28, cy + radius * 0.28),
                          radius * 0.30, radius * 0.20, angle=30,
                          facecolor="white", alpha=0.20,
                          zorder=zorder + 4))


def scatter_trees(ax, polygon_geoms, n_trees=None,
                  zorder=20, rng_seed=42):
    if not polygon_geoms:
        return
    merged = unary_union(polygon_geoms)
    if merged.is_empty:
        return
    area_m2 = merged.area
    if n_trees is None:
        n_trees = max(20, min(400, int(area_m2 / 220)))
    r   = max(2.5, min(8.0, (area_m2 / n_trees) ** 0.5 * 0.42))
    mbx, mby, mbx2, mby2 = merged.bounds
    rng = np.random.default_rng(rng_seed)
    species_list = list(TREE_SPECIES.keys())
    placed = attempts = 0
    while placed < n_trees and attempts < n_trees * 50:
        attempts += 1
        tx, ty = rng.uniform(mbx, mbx2), rng.uniform(mby, mby2)
        if merged.contains(Point(tx, ty)):
            sp    = rng.choice(species_list, p=[0.40, 0.25, 0.12, 0.12, 0.11])
            r_var = r * rng.uniform(0.65, 1.40)
            draw_tree(ax, tx, ty, r_var, species=sp,
                      zorder=zorder, rng=rng)
            placed += 1
    print(f"  🌳 Planted {placed} tree symbols  (r ≈ {r:.1f} m)")


# ── STEP 11: Road with pavement cross-section ─────────────────

def draw_road_pavement(ax, geom, road_half_width=4.5, zorder=30):
    lines = []
    if geom.geom_type == "LineString":
        lines = [geom]
    elif geom.geom_type == "MultiLineString":
        lines = list(geom.geoms)
    elif geom.geom_type == "Polygon":
        _fill_polygon(ax, geom, "#546E7A", alpha=0.90, zorder=zorder)
        return

    W = road_half_width
    for ls in lines:
        if ls.is_empty:
            continue
        try:
            w_walk   = W * 2.20
            w_kerb   = W * 1.18
            tarmac_b = ls.buffer(W,      cap_style=2, join_style=2)
            kerb_b   = ls.buffer(w_kerb, cap_style=2, join_style=2)
            walk_b   = ls.buffer(w_walk, cap_style=2, join_style=2)

            # Walkway
            walk_ring = walk_b.difference(kerb_b)
            _fill_polygon(ax, walk_ring, "#CFD8DC", alpha=0.80,
                          edgecolor="#90A4AE", lw=0.3, zorder=zorder)

            # Paving tile grid on walkway
            try:
                wx0, wy0, wx1, wy1 = walk_b.bounds
                step = W * 0.60
                for xv in np.arange(wx0, wx1, step):
                    seg = LineString([(xv, wy0-1), (xv, wy1+1)]).intersection(walk_ring)
                    if seg.is_empty:
                        continue
                    segs = [seg] if seg.geom_type == "LineString" else (
                           list(seg.geoms) if hasattr(seg, "geoms") else [])
                    for s in segs:
                        ax.plot(*s.xy, color="#B0BEC5", lw=0.22,
                                alpha=0.55, zorder=zorder + 1)
                for yv in np.arange(wy0, wy1, step):
                    seg = LineString([(wx0-1, yv), (wx1+1, yv)]).intersection(walk_ring)
                    if seg.is_empty:
                        continue
                    segs = [seg] if seg.geom_type == "LineString" else (
                           list(seg.geoms) if hasattr(seg, "geoms") else [])
                    for s in segs:
                        ax.plot(*s.xy, color="#B0BEC5", lw=0.22,
                                alpha=0.55, zorder=zorder + 1)
            except Exception:
                pass

            # Kerb strip
            kerb_ring = kerb_b.difference(tarmac_b)
            _fill_polygon(ax, kerb_ring, "#78909C", alpha=0.92,
                          edgecolor="#546E7A", lw=0.3, zorder=zorder + 2)

            # Tarmac
            _fill_polygon(ax, tarmac_b, "#455A64", alpha=0.95,
                          edgecolor="#37474F", lw=0.5, zorder=zorder + 3)

            # Bold kerb outline
            _draw_outline(ax, kerb_b, "#546E7A", lw=1.2,
                          alpha=0.9, zorder=zorder + 4)

            # Yellow edge lines
            for side in ["left", "right"]:
                try:
                    edge = ls.parallel_offset(W * 0.90, side)
                    if edge and not edge.is_empty:
                        ax.plot(*edge.xy, color="#FFEE58", lw=0.55,
                                alpha=0.80, zorder=zorder + 5,
                                solid_capstyle="round")
                except Exception:
                    pass

            # White centre dash
            ax.plot(*ls.xy, color="white", lw=0.65,
                    linestyle=(0, (8, 6)), alpha=0.80,
                    zorder=zorder + 6, solid_capstyle="round")

        except Exception as e:
            print(f"  ⚠ road error: {e}")


# ── STEP 12: Farm Pond with concrete/brick border ─────────────

def draw_farm_pond(ax, geom, zorder=25):
    for p in _get_polygons(geom):
        if p.is_empty:
            continue
        try:
            side      = p.area ** 0.5
            bw        = max(2.5, side * 0.045)
            outer_buf = p.buffer(bw)
            border    = outer_buf.difference(p)

            # Concrete border
            _fill_polygon(ax, border, "#9E9E9E", alpha=0.95,
                          edgecolor="#616161", lw=0.5,
                          hatch="..", zorder=zorder)

            # Brick joints
            bx0, by0, bx1, by1 = outer_buf.bounds
            bh, bww = bw * 0.55, bw * 1.1
            for by in np.arange(by0, by1, bh):
                seg = LineString([(bx0, by), (bx1, by)]).intersection(border)
                if seg.is_empty:
                    continue
                segs = [seg] if seg.geom_type == "LineString" else (
                       list(seg.geoms) if hasattr(seg, "geoms") else [])
                for s in segs:
                    ax.plot(*s.xy, color="#757575", lw=0.38,
                            alpha=0.70, zorder=zorder + 1)
            for bx in np.arange(bx0, bx1, bww):
                seg = LineString([(bx, by0), (bx, by1)]).intersection(border)
                if seg.is_empty:
                    continue
                segs = [seg] if seg.geom_type == "LineString" else (
                       list(seg.geoms) if hasattr(seg, "geoms") else [])
                for s in segs:
                    ax.plot(*s.xy, color="#757575", lw=0.38,
                            alpha=0.70, zorder=zorder + 1)

            _draw_outline(ax, outer_buf, "#424242", lw=2.0,
                          alpha=1.0, zorder=zorder + 2)

            # Water — 3 depth layers
            _fill_polygon(ax, p, "#1565C0", alpha=0.72, zorder=zorder + 3)
            sh = p.buffer(-bw * 0.5)
            if not sh.is_empty:
                _fill_polygon(ax, sh, "#1976D2", alpha=0.50, zorder=zorder + 4)
            dp = p.buffer(-bw * 1.2)
            if not dp.is_empty:
                _fill_polygon(ax, dp, "#0D47A1", alpha=0.50, zorder=zorder + 5)

            # Ripple arcs
            for rf in [0.30, 0.55, 0.75]:
                rip = p.centroid.buffer(side * rf).intersection(p)
                if not rip.is_empty:
                    _draw_outline(ax, rip, "#42A5F5", lw=0.45,
                                  alpha=0.38, zorder=zorder + 6,
                                  linestyle=(0, (4, 3)))
            _draw_outline(ax, p, "#1565C0", lw=1.0,
                          alpha=0.9, zorder=zorder + 7)

        except Exception as e:
            print(f"  ⚠ pond error: {e}")


# ── STEP 13: Jalkund ─────────────────────────────────────────

def draw_jalkund(ax, geom, zorder=26):
    for p in _get_polygons(geom):
        if p.is_empty:
            continue
        try:
            side      = p.area ** 0.5
            bw        = max(1.5, side * 0.08)
            outer_buf = p.buffer(bw)
            border    = outer_buf.difference(p)

            _fill_polygon(ax, border, "#78909C", alpha=0.92,
                          edgecolor="#546E7A", lw=0.6,
                          hatch="oo", zorder=zorder)
            _draw_outline(ax, outer_buf, "#37474F",
                          lw=1.8, alpha=0.95, zorder=zorder + 1)
            _fill_polygon(ax, p, "#29B6F6", alpha=0.80, zorder=zorder + 2)
            inn = p.buffer(-bw * 0.5)
            if not inn.is_empty:
                _fill_polygon(ax, inn, "#0288D1", alpha=0.60,
                              zorder=zorder + 3)
            _draw_outline(ax, p, "#0277BD",
                          lw=0.9, alpha=0.9, zorder=zorder + 4)
        except Exception as e:
            print(f"  ⚠ jalkund error: {e}")


# ── STEP 14: CNB (buffered to embankment polygon) ─────────────

def draw_cnb(ax, geom, buf_width=5.0, zorder=28):
    if geom.geom_type in ("LineString", "MultiLineString"):
        try:
            geom = geom.buffer(buf_width, cap_style=2, join_style=2)
        except Exception as e:
            print(f"  ⚠ CNB buffer error: {e}")
            return
    for p in _get_polygons(geom):
        if p.is_empty:
            continue
        try:
            _fill_polygon(ax, p, "#A1887F", alpha=0.88,
                          edgecolor="#6D4C41", lw=0.5, zorder=zorder)
            _fill_polygon(ax, p, "none", edgecolor="#5D4037",
                          lw=0.5, alpha=0.75, hatch="////",
                          zorder=zorder + 1)
            _draw_outline(ax, p, "#4E342E", lw=2.5,
                          alpha=0.95, zorder=zorder + 2)
            inn = p.buffer(-buf_width * 0.35)
            if not inn.is_empty:
                _draw_outline(ax, inn, "#795548", lw=0.7,
                              alpha=0.65, zorder=zorder + 3,
                              linestyle=(0, (4, 3)))
            c = p.centroid
            ax.text(c.x, c.y, "CNB", fontsize=6.5,
                    ha="center", va="center", fontweight="bold",
                    color="#3E2723", zorder=zorder + 4,
                    bbox=dict(facecolor="#EFEBE9", alpha=0.80,
                              pad=2, edgecolor="#795548",
                              linewidth=0.6, boxstyle="round,pad=0.3"))
        except Exception as e:
            print(f"  ⚠ CNB draw error: {e}")


# ── STEP 15: Figure ───────────────────────────────────────────

fig_w, fig_h = 24, 18
fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=200)
fig.patch.set_facecolor("#F0EDE6")
ax.set_facecolor("#E8F5E9")   # fallback bg colour

ax.set_xlim(minx - margin, maxx + margin)
ax.set_ylim(miny - margin, maxy + margin)
ax.set_aspect("equal")


# ── STEP 16: Basemap (3 methods, auto-fallback) ───────────────

# Patch contextily session
_sess = requests.Session()
_sess.verify = False
_sess.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
})
try:
    import contextily.tile as _ct
    _ct._session = _sess
except Exception:
    pass

# Auto-zoom from bounding box
_W, _S = _T_INV.transform(minx - margin, miny - margin)
_E, _N = _T_INV.transform(maxx + margin, maxy + margin)
_span  = max(_E - _W, _N - _S)
if   _span < 0.005: _zoom = 17
elif _span < 0.015: _zoom = 16
elif _span < 0.040: _zoom = 15
elif _span < 0.100: _zoom = 14
elif _span < 0.300: _zoom = 13
else:               _zoom = 12

print(f"\n🌍 Basemap fetch  zoom={_zoom}  "
      f"lon[{_W:.4f},{_E:.4f}]  lat[{_S:.4f},{_N:.4f}]")

_PROVIDERS = [
    ("ESRI Topo",      ctx.providers.Esri.WorldTopoMap),
    ("ESRI Hillshade", ctx.providers.Esri.WorldShadedRelief),
    ("ESRI Imagery",   ctx.providers.Esri.WorldImagery),
    ("OSM",            ctx.providers.OpenStreetMap.Mapnik),
]

_basemap_ok = False

# Method A: bounds2img
for _name, _src in _PROVIDERS:
    try:
        _img, _ext = ctx.bounds2img(
            minx - margin, miny - margin,
            maxx + margin, maxy + margin,
            zoom=_zoom, source=_src, ll=False,
        )
        ax.imshow(_img, extent=_ext, origin="upper",
                  alpha=0.68, zorder=1, interpolation="bilinear")
        print(f"✅ Basemap loaded (bounds2img): {_name}")
        _basemap_ok = True
        break
    except Exception as _e:
        print(f"  ⚠ bounds2img {_name}: {_e}")

# Method B: manual tile stitch
if not _basemap_ok:
    print("  🔄 Trying manual tile stitch (OSM)…")
    try:
        _TILE_URLS = [
            "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            "https://a.tile.openstreetmap.fr/osmfr/{z}/{x}/{y}.png",
        ]
        _tiles  = list(mercantile.tiles(_W, _S, _E, _N, zooms=_zoom))
        _TSIZE  = 256
        _xs     = [t.x for t in _tiles]
        _ys     = [t.y for t in _tiles]
        _mnx_t, _mxx_t = min(_xs), max(_xs)
        _mny_t, _mxy_t = min(_ys), max(_ys)
        _cols   = _mxx_t - _mnx_t + 1
        _rows   = _mxy_t - _mny_t + 1
        _canvas = PILImage.new("RGBA",
                               (_cols * _TSIZE, _rows * _TSIZE),
                               (236, 240, 234, 255))
        _fetched = 0
        for _t in _tiles:
            for _url_tmpl in _TILE_URLS:
                _url = _url_tmpl.format(z=_t.z, x=_t.x, y=_t.y)
                try:
                    _r = _sess.get(_url, timeout=9)
                    if _r.status_code == 200:
                        _tile_img = PILImage.open(
                            io.BytesIO(_r.content)).convert("RGBA")
                        _px = (_t.x - _mnx_t) * _TSIZE
                        _py = (_t.y - _mny_t) * _TSIZE
                        _canvas.paste(_tile_img, (_px, _py))
                        _fetched += 1
                        break
                except Exception:
                    pass
        if _fetched > 0:
            _ul   = mercantile.ul(_mnx_t,     _mny_t,     _zoom)
            _lr   = mercantile.ul(_mxx_t + 1, _mxy_t + 1, _zoom)
            _x0c, _y1c = _T_FWD.transform(_ul.lng, _ul.lat)
            _x1c, _y0c = _T_FWD.transform(_lr.lng, _lr.lat)
            ax.imshow(np.array(_canvas),
                      extent=[_x0c, _x1c, _y0c, _y1c],
                      origin="upper", alpha=0.68, zorder=1,
                      interpolation="bilinear")
            print(f"✅ Basemap via tile stitch: {_fetched}/{len(_tiles)} tiles")
            _basemap_ok = True
        else:
            print("  ⚠ No tiles fetched.")
    except Exception as _e2:
        print(f"  ⚠ tile stitch failed: {_e2}")

# Method C: terrain gradient fallback
if not _basemap_ok:
    print("  ℹ Rendering terrain gradient fallback…")
    _h, _w = 500, 600
    _Y2, _X2 = np.mgrid[0:_h, 0:_w]
    _terr  = (_X2 / _w * 0.5 + _Y2 / _h * 0.5
              + 0.12 * np.sin(_X2 / _w * 14) * np.cos(_Y2 / _h * 11))
    _terr += np.random.rand(_h, _w) * 0.04
    _terr  = gaussian_filter(_terr, sigma=7)
    _ext2  = [minx - margin, maxx + margin,
              miny - margin, maxy + margin]
    ax.imshow(_terr, extent=_ext2, origin="lower", cmap="terrain",
              alpha=0.45, aspect="auto", zorder=1,
              interpolation="bilinear")
    _Xg = np.linspace(_ext2[0], _ext2[1], _w)
    _Yg = np.linspace(_ext2[2], _ext2[3], _h)
    _Xm, _Ym = np.meshgrid(_Xg, _Yg)
    ax.contour(_Xm, _Ym, _terr, levels=10,
               colors=["#78909C"], alpha=0.28,
               linewidths=0.35, zorder=2)
    print("✅ Terrain gradient rendered.")


# ── STEP 17: Site boundary ─────────────────────────────────────
hull = combined.convex_hull.buffer(margin * 0.55)
_fill_polygon(ax, hull, "#FFFFFF", alpha=0.05, zorder=3)
_draw_outline(ax, hull, "#FF6F00", lw=2.0, alpha=0.70,
              zorder=4, linestyle=(0, (8, 4)))


# ── STEP 18: Draw all layers ───────────────────────────────────

# Plantation on CCT base fill
for feat in layers["plantation_cct"]:
    g = feat.get("geometry")
    if g:
        _fill_polygon(ax, g, "#C8E6C9", alpha=0.78,
                      edgecolor="#388E3C", lw=0.9,
                      hatch="//", zorder=18)

# Plantation base fill + collect polygons for trees
plantation_polys = []
for feat in layers["plantation"]:
    g = feat.get("geometry")
    if g and not g.is_empty:
        for p in _get_polygons(g):
            _fill_polygon(ax, p, "#388E3C", alpha=0.35,
                          edgecolor="#2E7D32", lw=1.0, zorder=17)
            plantation_polys.append(p)

# Tree symbols on plantations
scatter_trees(ax, plantation_polys, zorder=22)

# Tree symbols on CCT zones
cct_polys = []
for feat in layers["plantation_cct"]:
    g = feat.get("geometry")
    if g:
        cct_polys.extend(_get_polygons(g))
scatter_trees(ax, cct_polys, n_trees=max(5, len(cct_polys) * 8),
              zorder=21, rng_seed=77)

# Farm ponds
for feat in layers["farm_pond"]:
    g = feat.get("geometry")
    if g:
        draw_farm_pond(ax, g, zorder=25)

# Jalkund
for feat in layers["jalkund"]:
    g = feat.get("geometry")
    if g:
        draw_jalkund(ax, g, zorder=26)

# CNB
for feat in layers["cnb"]:
    g = feat.get("geometry")
    if g:
        draw_cnb(ax, g, buf_width=5.5, zorder=28)

# Roads (drawn last, on top)
for feat in layers["road"]:
    g = feat.get("geometry")
    if g:
        draw_road_pavement(ax, g, road_half_width=4.5, zorder=32)

# Other
for feat in layers["other"]:
    g = feat.get("geometry")
    if g and not g.is_empty:
        _fill_polygon(ax, g, "#CFD8DC", alpha=0.55,
                      edgecolor="#546E7A", lw=0.6, zorder=8)


# ── STEP 19: Grid (AutoCAD-style) ─────────────────────────────
span_m    = max(maxx - minx, maxy - miny)
raw_step  = span_m / 8
for snap in [25, 50, 100, 200, 500, 1000]:
    if raw_step <= snap:
        grid_step = snap
        break
else:
    grid_step = 1000

xs_grid = np.arange(
    np.floor((minx - margin) / grid_step) * grid_step,
    maxx + margin + grid_step, grid_step)
ys_grid = np.arange(
    np.floor((miny - margin) / grid_step) * grid_step,
    maxy + margin + grid_step, grid_step)

for xg in xs_grid:
    ax.axvline(xg, color="#546E7A", lw=0.35, alpha=0.50, zorder=6)
for yg in ys_grid:
    ax.axhline(yg, color="#546E7A", lw=0.35, alpha=0.50, zorder=6)

for xg in xs_grid:
    for yg in ys_grid:
        t = grid_step * 0.10
        ax.plot([xg - t, xg + t], [yg, yg],
                color="#37474F", lw=0.9, alpha=0.75, zorder=7)
        ax.plot([xg, xg], [yg - t, yg + t],
                color="#37474F", lw=0.9, alpha=0.75, zorder=7)

ax.set_xticks(xs_grid)
ax.set_yticks(ys_grid)
ax.xaxis.set_major_formatter(
    ticker.FuncFormatter(lambda v, _: f"{v:.0f} m"))
ax.yaxis.set_major_formatter(
    ticker.FuncFormatter(lambda v, _: f"{v:.0f} m"))
ax.tick_params(axis="both", labelsize=6.5, colors="#37474F",
               length=4, width=0.7, direction="in",
               top=True, right=True)
for spine in ax.spines.values():
    spine.set_edgecolor("#37474F")
    spine.set_linewidth(1.5)

ax.set_xlabel("Easting  (EPSG:3857, metres)",
              fontsize=8, color="#37474F", labelpad=7)
ax.set_ylabel("Northing  (EPSG:3857, metres)",
              fontsize=8, color="#37474F", labelpad=7)


# ── STEP 20: Scale bar (anchored, non-overlapping) ─────────────

def add_scale_bar(ax, seg_len_m, fontsize=8):
    """Scale bar in axes-fraction coords — never overlaps features."""
    # White backing box
    ax.add_patch(FancyBboxPatch(
        (0.015, 0.020), 0.230, 0.068,
        transform=ax.transAxes, clip_on=False,
        boxstyle="round,pad=0.008",
        facecolor="white", edgecolor="#546E7A",
        linewidth=0.9, alpha=0.92, zorder=48))

    bar_x0   = 0.025    # left edge
    bar_y0   = 0.028    # bottom
    bar_y1   = 0.044    # top
    seg_frac = 0.062    # fraction width per segment

    colors = ["#1A1A1A", "white", "#1A1A1A"]
    for i, fc in enumerate(colors):
        ax.add_patch(FancyBboxPatch(
            (bar_x0 + i * seg_frac, bar_y0),
            seg_frac, bar_y1 - bar_y0,
            transform=ax.transAxes, clip_on=False,
            boxstyle="square,pad=0",
            facecolor=fc, edgecolor="#1A1A1A",
            linewidth=0.6, zorder=49))

    # Tick labels
    for i, lbl in enumerate(["0",
                               f"{seg_len_m:.0f} m",
                               f"{seg_len_m*2:.0f} m",
                               f"{seg_len_m*3:.0f} m"]):
        ax.text(bar_x0 + i * seg_frac, bar_y0 - 0.005,
                lbl, transform=ax.transAxes,
                ha="center", va="top", fontsize=fontsize - 0.5,
                color="#1A1A1A", zorder=50,
                fontfamily="monospace")

    # Header
    ax.text(bar_x0 + 1.5 * seg_frac, bar_y1 + 0.005,
            f"1 seg = {seg_len_m:.0f} m",
            transform=ax.transAxes,
            ha="center", va="bottom",
            fontsize=fontsize - 1.2, color="#37474F",
            zorder=50, fontstyle="italic")


add_scale_bar(ax, grid_step * 2, fontsize=8)


# ── STEP 21: North arrow ──────────────────────────────────────

def add_north_arrow(ax, x=0.965, y=0.855, length=0.046):
    ax.annotate("", xy=(x, y + length), xytext=(x, y),
                xycoords="axes fraction",
                textcoords="axes fraction",
                arrowprops=dict(arrowstyle="-|>", color="#212121",
                                lw=2.0, mutation_scale=16))
    ax.text(x, y + length + 0.015, "N",
            transform=ax.transAxes,
            ha="center", va="bottom",
            fontsize=12, fontweight="bold",
            color="#212121", fontfamily="serif")

add_north_arrow(ax)


# ── STEP 22: Legend ───────────────────────────────────────────

legend_defs = [
    ("Plantation",          "#388E3C", "#2E7D32", None,  "patch"),
    ("Plantation on CCT",   "#C8E6C9", "#388E3C", "//",  "patch"),
    ("Farm Pond",           "#1565C0", "#424242", "..",  "patch"),
    ("Jalkund",             "#29B6F6", "#37474F", "oo",  "patch"),
    ("CNB (Nala Bund)",     "#A1887F", "#5D4037", "////","patch"),
    ("Park Road / Walkway", "#455A64", "#37474F", None,  "line"),
    ("Tree Canopy",         "#66BB6A", "#2E7D32", None,  "tree"),
    ("Site Boundary",       None,      "#FF6F00", None,  "dash"),
]
handles = []
for label, fc, ec, hatch, kind in legend_defs:
    if kind == "patch":
        h = mpatches.Patch(facecolor=fc, edgecolor=ec,
                           hatch=hatch, label=label, linewidth=0.7)
    elif kind == "line":
        h = Line2D([0], [0], color=ec, linewidth=2, label=label)
    elif kind == "dash":
        h = Line2D([0], [0], color=ec, linewidth=1.6,
                   linestyle="--", label=label)
    else:  # tree
        h = Line2D([0], [0], marker="o", color="none",
                   markerfacecolor=fc, markeredgecolor=ec,
                   markersize=9, label=label)
    handles.append(h)

leg = ax.legend(
    handles=handles, loc="lower right",
    title="L E G E N D", title_fontsize=9,
    fontsize=7.8, frameon=True, framealpha=0.93,
    edgecolor="#546E7A", facecolor="#FAFAFA",
    handlelength=2.2, handleheight=1.5,
    borderpad=1.0, labelspacing=0.60)
leg.get_title().set_fontweight("bold")
leg.get_title().set_color("#1B5E20")
leg.get_frame().set_linewidth(1.2)


# ── STEP 23: Feature summary box ─────────────────────────────

sum_lines = ["FEATURE SUMMARY"]
for k, feats in layers.items():
    n = len(feats)
    if n:
        sum_lines.append(f"  {LAYER_LABELS[k]}: {n}")
ax.text(0.012, 0.985, "\n".join(sum_lines),
        transform=ax.transAxes, fontsize=7.0,
        va="top", ha="left",
        bbox=dict(boxstyle="round,pad=0.5",
                  facecolor="#FFFDE7",
                  edgecolor="#546E7A",
                  alpha=0.90, linewidth=0.8),
        color="#1B5E20", fontfamily="monospace",
        zorder=45, linespacing=1.5)


# ── STEP 24: Title & footer ───────────────────────────────────

fig.add_artist(FancyBboxPatch(
    (0.0, 0.948), 1.0, 0.052,
    transform=fig.transFigure, clip_on=False,
    boxstyle="square,pad=0",
    facecolor="#1B5E20", edgecolor="none", zorder=50))
fig.text(0.5, 0.9745,
         "BIODIVERSITY PARK — PROPOSED LAYOUT PLAN",
         ha="center", va="center", fontsize=17,
         fontweight="bold", color="white",
         zorder=51, fontfamily="serif",
         transform=fig.transFigure)
_bm_label = ("ESRI World Topo" if _basemap_ok else "terrain gradient")
fig.text(0.5, 0.9565,
         f"Plantation  ●  Plantation on CCT  ●  Farm Ponds  ●  "
         f"Jalkund  ●  CNB  ●  Park Roads  ●  Basemap: {_bm_label}",
         ha="center", va="center", fontsize=7.5,
         color="#A5D6A7", transform=fig.transFigure, zorder=51)

fig.add_artist(FancyBboxPatch(
    (0.0, 0.0), 1.0, 0.026,
    transform=fig.transFigure, clip_on=False,
    boxstyle="square,pad=0",
    facecolor="#1B5E20", edgecolor="none", zorder=50))
fig.text(0.02, 0.013,
         "Prepared using Python + Matplotlib + Contextily  |  KML source data",
         ha="left", va="center", fontsize=6.5,
         color="#A5D6A7", transform=fig.transFigure, zorder=51)
fig.text(0.5, 0.013,
         f"Projection: EPSG:3857 (Web Mercator)  |  "
         f"Grid interval: {grid_step:.0f} m",
         ha="center", va="center", fontsize=6.5,
         color="#A5D6A7", transform=fig.transFigure, zorder=51)
fig.text(0.98, 0.013, "Date: 21-05-2026",
         ha="right", va="center", fontsize=6.5,
         color="#A5D6A7", transform=fig.transFigure, zorder=51)


# ── STEP 25: Save & download ──────────────────────────────────

plt.tight_layout(rect=[0, 0.026, 1, 0.948])

OUT = "biodiversity_park_layout_v3"
fig.savefig(f"{OUT}.png", dpi=220, bbox_inches="tight",
            facecolor=fig.get_facecolor())
print(f"\n✅ Saved → {OUT}.png  (220 dpi)")

fig.savefig(f"{OUT}.pdf", bbox_inches="tight",
            facecolor=fig.get_facecolor())
print(f"✅ Saved → {OUT}.pdf  (vector PDF)")

plt.show()

if IN_COLAB:
    colab_files.download(f"{OUT}.png")
    colab_files.download(f"{OUT}.pdf")
    print("\n📥 Downloads started!")

print("\n🎉 Biodiversity Park Layout Plan v3 complete!")
#!/usr/bin/env python3
"""Static figures for the January 2025 Los Angeles fires, from GOES-18 fire detections.

Inputs (all in data/ next to this script)
  la_2025.csv, la_2025_scans.csv     GOES-18 FDCC fire pixels, from scripts/extract_fdc.py
  la_2025_goes16_first48h*.csv       GOES-16 FDCC, first 48 hours only, as an independent check
  perimeters_la_2025.geojson         NIFC WFIGS final perimeters
  land_la.geojson                    Natural Earth 10 m land, clipped to the area

Outputs, next to this script
  la_01_overview_map.png ... la_07_detection_time.png, la_2025_summary.csv

Processing reuses scripts/build_fires.py (persistence filter, gap fill, attribution,
connected spread), so the numbers mean the same thing as on the web page. Times are
Pacific Standard Time (UTC-8), the clock residents used, instead of solar time.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.collections import PolyCollection
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from matplotlib.ticker import FuncFormatter
from shapely.geometry import shape

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
sys.path.insert(0, str(HERE.parent.parent / "scripts"))
import build_fires as bf  # noqa: E402

PST = pd.Timedelta(hours=-8)
START = pd.Timestamp("2025-01-07 00:00")      # PST, naive
END = pd.Timestamp("2025-02-01 00:00")
UTC = lambda s: pd.Timestamp(s, tz="UTC")  # noqa: E731

# id, label, perimeter name in NIFC, origin (NIFC incident location point)
FIRES = [
    ("palisades", "Palisades", "PALISADES", (34.0677778, -118.5511111)),
    ("eaton", "Eaton", "Eaton", (34.19163, -118.10544)),
    ("hughes", "Hughes", "Hughes", (34.551719, -118.57574)),
    ("kenneth", "Kenneth", "KENNETH", (34.1855556, -118.6688889)),
    ("hurst", "Hurst", "Hurst", (34.3261111, -118.4622222)),
    ("auto", "Auto", "Auto", None),
    ("laguna", "Laguna", "Laguna", None),
]
# Fires with no NIFC perimeter. Unassigned pixels near the point, in the time window, join them.
POINT_FIRES = {
    # NIFC incident location point and discovery time
    "lidia": dict(label="Lidia", lat=34.43891, lon=-118.23118, km=6.0,
                  start=UTC("2025-01-08 20:59:38"), until=UTC("2025-01-20")),
    # No NIFC record. Location near Runyon Canyon and ~5:30 p.m. start from news reports (README)
    "sunset": dict(label="Sunset", lat=34.112, lon=-118.350, km=4.0,
                   start=UTC("2025-01-09 01:30"), until=UTC("2025-01-09 16:00")),
}
MAIN = ["palisades", "eaton", "hughes"]
LABEL = {fid: label for fid, label, _, _ in FIRES} | {k: v["label"] for k, v in POINT_FIRES.items()}

# Reported start, earliest and latest across sources (PST). Sources in README.md.
REPORTED = {
    "palisades": ("2025-01-07 10:30", "2025-01-07 10:30"),
    "eaton": ("2025-01-07 18:15", "2025-01-07 18:19"),
    "hurst": ("2025-01-07 22:10", "2025-01-07 22:30"),
    "lidia": ("2025-01-08 12:59", "2025-01-08 12:59"),
    "sunset": ("2025-01-08 17:30", "2025-01-08 17:30"),
    "kenneth": ("2025-01-09 14:30", "2025-01-09 15:34"),
    "auto": ("2025-01-13 18:50", "2025-01-13 18:50"),
    "hughes": ("2025-01-22 10:30", "2025-01-22 10:53"),
}

# Palette: first three categorical slots of the reference palette, validated
# all-pairs (light). Aqua is under 3:1 on the surface, so every aqua mark is direct-labelled.
COLOR = {"palisades": "#2a78d6", "eaton": "#eb6834", "hughes": "#1baf7a", "other": "#8a8984", "none": "#c9c8c2"}
SURFACE, INK, INK2, MUTED = "#fcfcfb", "#0b0b0b", "#52514e", "#8a8984"
GRID, LAND, NIGHT, COAST = "#e6e5e0", "#efeee9", "#eceae4", "#c9c8c2"
# Ordinal blue steps 700, 550, 400, 250 (lightest step allowed on a light surface)
BLUES = ["#0d366b", "#1c5cab", "#3987e5", "#86b6ef"]
BINS = [0, 3, 12, 48, 10_000]
BIN_LABELS = ["First 3 hours", "3 to 12 hours", "12 to 48 hours", "After 2 days"]

plt.rcParams.update({
    "font.family": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9, "axes.titlesize": 10.5, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.titlecolor": INK, "axes.labelcolor": INK2, "axes.edgecolor": COAST, "axes.linewidth": 0.8,
    "xtick.color": INK2, "ytick.color": INK2, "xtick.major.size": 0, "ytick.major.size": 0,
    "axes.spines.top": False, "axes.spines.right": False, "axes.spines.left": False,
    "axes.grid": True, "axes.grid.axis": "y", "axes.axisbelow": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "grid.linestyle": "-",
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "legend.frameon": False, "legend.fontsize": 8.5, "lines.linewidth": 1.6,
})
THOUSANDS = FuncFormatter(lambda v, _: f"{v:,.0f}")

# Events used as annotations (PST; sources in README.md)
RAIN = pd.Timestamp("2025-01-26 00:00")
CONTAINED = pd.Timestamp("2025-01-31 12:00")


# ---------------------------------------------------------------- data

def load():
    det = pd.read_csv(DATA / "la_2025.csv", parse_dates=["time"])
    scans = pd.read_csv(DATA / "la_2025_scans.csv", parse_dates=["time"])
    perims = bf.load_perimeters(DATA / "perimeters_la_2025.geojson")
    for fid, _, name, origin in FIRES:
        if origin:
            perims[name]["lat"], perims[name]["lon"] = origin

    n_raw = len(det)
    d = bf.drop_one_off_pixels(det)
    d["utc_hour"] = d.time.dt.floor("h")
    d = bf.fill_frp(d)
    bf.FIRES = [(fid, label, "", name) for fid, label, name, _ in FIRES]
    d["fire"] = pd.Series(bf.attribute(d, perims), index=d.index).fillna("none")
    for fid, p in POINT_FIRES.items():
        near = bf.haversine_km(p["lat"], p["lon"], d.lat.values, d.lon.values) <= p["km"]
        window = (d.time >= p["start"] - pd.Timedelta("1h")) & (d.time < p["until"])
        d.loc[(d.fire == "none") & near & window, "fire"] = fid
    d["pst"] = (d.time + PST).dt.tz_localize(None)
    scans["pst"] = (scans.time + PST).dt.tz_localize(None)
    return d, scans, perims, n_raw


def rate(d, scans, freq, t0=START, t1=END):
    """Fire radiative power per bin, in GW, averaged over the scans in that bin (FRP is a rate).
    NaN where no scan arrived."""
    n = scans.groupby(scans.pst.dt.floor(freq)).size()
    idx = pd.date_range(t0, t1, freq=freq, inclusive="left")
    n = n.reindex(idx)
    cols = [c for c in ("frp_filled", "frp_mw") if c in d]
    return pd.DataFrame({c: d.groupby(d.pst.dt.floor(freq))[c].sum().reindex(idx, fill_value=0) / n / 1000
                         for c in cols})


def energy_tj(hourly_gw):
    """Fire radiative energy from hourly mean power: GW x 3600 s = TJ."""
    return float(hourly_gw.fillna(0).sum() * 3.6)


def sun_elevation(ts, lat, lon):
    """Approximate solar elevation in degrees (NOAA low-precision formulas). ts is naive UTC."""
    ts = pd.DatetimeIndex(ts)
    doy = ts.dayofyear.values
    hr = ts.hour.values + ts.minute.values / 60
    g = 2 * np.pi / 365 * (doy - 1 + (hr - 12) / 24)
    eqt = 229.18 * (0.000075 + 0.001868 * np.cos(g) - 0.032077 * np.sin(g)
                    - 0.014615 * np.cos(2 * g) - 0.040849 * np.sin(2 * g))
    decl = (0.006918 - 0.399912 * np.cos(g) + 0.070257 * np.sin(g) - 0.006758 * np.cos(2 * g)
            + 0.000907 * np.sin(2 * g) - 0.002697 * np.cos(3 * g) + 0.00148 * np.sin(3 * g))
    ha = np.radians((hr * 60 + eqt + 4 * np.asarray(lon)) / 4 - 180)
    la = np.radians(lat)
    cosz = np.sin(la) * np.sin(decl) + np.cos(la) * np.cos(decl) * np.cos(ha)
    return 90 - np.degrees(np.arccos(np.clip(cosz, -1, 1)))


def night_spans(t0, t1, lat=34.1, lon=-118.3):
    """(start, end) PST spans where the sun is below the horizon."""
    t = pd.date_range(t0, t1, freq="5min")
    dark = sun_elevation(t - PST, lat, lon) < 0
    spans, start = [], None
    for ti, dk in zip(t, dark):
        if dk and start is None:
            start = ti
        if not dk and start is not None:
            spans.append((start, ti))
            start = None
    if start is not None:
        spans.append((start, t[-1]))
    return spans


# ---------------------------------------------------------------- pixel footprints

G18 = dict(h=35786023.0 + 6378137.0, rq=6378137.0, rp=6356752.31414, lon0=-137.0, ifov=56e-6)


def latlon_to_scan(lat, lon):
    rq, rp, H = G18["rq"], G18["rp"], G18["h"]
    e2 = 1 - (rp / rq) ** 2
    phi = np.arctan((rp / rq) ** 2 * np.tan(np.radians(lat)))
    rc = rp / np.sqrt(1 - e2 * np.cos(phi) ** 2)
    dl = np.radians(lon - G18["lon0"])
    sx, sy, sz = H - rc * np.cos(phi) * np.cos(dl), -rc * np.cos(phi) * np.sin(dl), rc * np.sin(phi)
    return np.arcsin(-sy / np.sqrt(sx ** 2 + sy ** 2 + sz ** 2)), np.arctan(sz / sx)


def scan_to_latlon(x, y):
    rq, rp, H = G18["rq"], G18["rp"], G18["h"]
    a = np.sin(x) ** 2 + np.cos(x) ** 2 * (np.cos(y) ** 2 + (rq / rp) ** 2 * np.sin(y) ** 2)
    b = -2 * H * np.cos(x) * np.cos(y)
    c = H ** 2 - rq ** 2
    rs = (-b - np.sqrt(b * b - 4 * a * c)) / (2 * a)
    sx, sy, sz = rs * np.cos(x) * np.cos(y), -rs * np.sin(x), rs * np.cos(x) * np.sin(y)
    lat = np.degrees(np.arctan((rq / rp) ** 2 * sz / np.sqrt((H - sx) ** 2 + sy ** 2)))
    lon = G18["lon0"] - np.degrees(np.arctan(sy / (H - sx)))
    return lat, lon


def footprints(lat, lon):
    """Corner polygons [(lon, lat) x 4] for each pixel centre, from the GOES-18 fixed grid."""
    x, y = latlon_to_scan(np.asarray(lat), np.asarray(lon))
    h = G18["ifov"] / 2
    corners = [scan_to_latlon(x + dx, y + dy) for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h))]
    return np.stack([np.stack([lo, la], axis=1) for la, lo in corners], axis=1)


def pixel_km(lat, lon):
    poly = footprints([lat], [lon])[0]
    k = np.cos(np.radians(lat)) * bf.KM_PER_DEG
    w = np.hypot((poly[1, 0] - poly[0, 0]) * k, (poly[1, 1] - poly[0, 1]) * bf.KM_PER_DEG)
    h = np.hypot((poly[3, 0] - poly[0, 0]) * k, (poly[3, 1] - poly[0, 1]) * bf.KM_PER_DEG)
    return w, h


# ---------------------------------------------------------------- drawing helpers

def save(fig, name):
    fig.savefig(HERE / name, dpi=200, bbox_inches="tight", pad_inches=0.25)
    plt.close(fig)
    print("wrote", name)


def clock(t):
    return f"{t:%-I:%M %p}".replace("AM", "a.m.").replace("PM", "p.m.").replace(":00 ", " ")


def title_block(fig, title, subtitle=None, y=0.995):
    fig.text(0.01, y, title, ha="left", va="top", fontsize=12.5, fontweight="bold", color=INK)
    if subtitle:
        fig.text(0.01, y - 0.055, subtitle, ha="left", va="top", fontsize=9, color=INK2)


def footnote(fig, text, y=0.0):
    fig.text(0.01, y, text, ha="left", va="top", fontsize=7.5, color=MUTED, wrap=True)


def shade_nights(ax, t0, t1):
    for a, b in night_spans(t0, t1):
        ax.axvspan(a, b, color=NIGHT, lw=0, zorder=0)


def draw_base(ax, land, extent):
    w, e, s, n = extent
    for g in getattr(land, "geoms", [land]):
        ax.fill(*g.exterior.xy, color=LAND, lw=0, zorder=0)
        ax.plot(*g.exterior.xy, color=COAST, lw=0.6, zorder=1)
    ax.set_xlim(w, e)
    ax.set_ylim(s, n)
    ax.set_aspect(1 / np.cos(np.radians((s + n) / 2)))
    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid(False)
    for side in ax.spines.values():
        side.set_visible(False)


def draw_outline(ax, geom, lw=0.9):
    for g in getattr(geom, "geoms", [geom]):
        ax.plot(*g.exterior.xy, color=INK, lw=lw, zorder=4)


def draw_origin(ax, lat, lon):
    ax.plot(lon, lat, "o", ms=8, mfc=SURFACE, mec=INK, mew=1.4, zorder=6)


def scale_bar(ax, km, lat, where="left"):
    w, e = ax.get_xlim()
    s, n = ax.get_ylim()
    deg = km / (bf.KM_PER_DEG * np.cos(np.radians(lat)))
    x0 = w + (e - w) * 0.05 if where == "left" else e - (e - w) * 0.05 - deg
    y0 = s + (n - s) * 0.05
    ax.plot([x0, x0 + deg], [y0, y0], color=INK, lw=1.6, solid_capstyle="butt", zorder=7)
    ax.text(x0 + deg / 2, y0 + (n - s) * 0.02, f"{km} km", ha="center", va="bottom", fontsize=8, color=INK2, zorder=7)


# ---------------------------------------------------------------- figures

def fig_overview(d, perims, land):
    """Every kept fire pixel over the whole period, by fire."""
    extent = (-119.27, -117.85, 33.93, 34.72)
    fig, ax = plt.subplots(figsize=(10.5, 6.4))
    fig.subplots_adjust(top=0.86, bottom=0.08)
    draw_base(ax, land, extent)
    px = d.groupby(["lat", "lon"]).fire.agg(lambda s: s.mode().iat[0]).reset_index()
    polys = footprints(px.lat.values, px.lon.values)
    group = {f: (f if f in MAIN or f == "none" else "other") for f in px.fire.unique()}
    ax.add_collection(PolyCollection(polys, facecolors=[COLOR[group[f]] for f in px.fire],
                                     edgecolors=SURFACE, linewidths=0.3, zorder=3))
    seen = set(px.fire)
    for fid, label, name, origin in FIRES:
        if name in perims and fid in seen:
            draw_outline(ax, perims[name]["geom"], lw=0.7)

    # Each label sits beside its fire's pixels and perimeter, on the side with open space.
    side = {"palisades": "below", "eaton": "below", "hughes": "left", "kenneth": "left",
            "hurst": "left", "lidia": "right", "sunset": "below", "auto": "right", "laguna": "right"}
    off = {"below": (0, -7, "center", "top"), "left": (-7, 0, "right", "center"), "right": (7, 0, "left", "center")}
    for fid, where in side.items():
        if fid not in seen:
            continue
        sel = polys[(px.fire == fid).values].reshape(-1, 2)
        xs, ys = list(sel[:, 0]), list(sel[:, 1])
        name = next((n for f, _, n, _ in FIRES if f == fid), None)
        if name in perims:
            b = perims[name]["geom"].bounds
            xs += [b[0], b[2]]
            ys += [b[1], b[3]]
        anchor = {"below": ((min(xs) + max(xs)) / 2, min(ys)), "left": (min(xs), (min(ys) + max(ys)) / 2),
                  "right": (max(xs), (min(ys) + max(ys)) / 2)}[where]
        dx, dy, ha, va = off[where]
        acres = (f"{perims[name]['acres']:,.0f} acres" if name in perims
                 else "about 43 acres (news)" if fid == "sunset" else "no NIFC perimeter")
        big = fid in MAIN
        ax.annotate(f"{LABEL[fid]}\n{acres}", anchor, xytext=(dx, dy), textcoords="offset points",
                    fontsize=9.5 if big else 8, fontweight="bold" if big else "normal",
                    color=INK if big else INK2, ha=ha, va=va, zorder=8, linespacing=1.2)
    ax.text(-118.97, 33.96, "Pacific Ocean", fontsize=8, color=MUTED, style="italic", va="bottom")
    scale_bar(ax, 20, 34.3, where="right")
    handles = [Patch(color=COLOR[f], label=LABEL[f]) for f in MAIN]
    handles += [Patch(color=COLOR["other"], label="Smaller named fires"),
                Patch(color=COLOR["none"], label="Not matched to a fire"),
                Line2D([], [], color=INK, lw=0.9, label="Official final perimeter")]
    ax.legend(handles=handles, loc="upper right", handlelength=1.2, borderaxespad=0.4, fontsize=8)
    title_block(fig, "Where GOES-18 saw fire around Los Angeles, January 7 to 31, 2025",
                "Every 2–3 km pixel the satellite flagged as fire at least twice within 2 hours, at its true footprint",
                y=0.97)
    unseen = [f"{LABEL[f]} ({perims[n]['acres']:,.0f} acres)" for f, _, n, _ in FIRES if f not in seen and n in perims]
    note = ("Pixel footprints come from the GOES-18 fixed grid (about 2.3 by 2.8 km here). Perimeters: NIFC WFIGS. "
            "Land: Natural Earth.")
    if unseen:
        note += f" {' and '.join(unseen)} never produced a kept pixel."
    footnote(fig, note, y=0.06)
    save(fig, "la_01_overview_map.png")


def fig_spread_maps(d, perims, land):
    """First time each pixel was seen, in hours after the reported start."""
    fig, axes = plt.subplots(1, 3, figsize=(13, 6.3))
    fig.subplots_adjust(top=0.79, bottom=0.12, left=0.01, right=0.99, wspace=0.06)
    for ax, fid in zip(axes, MAIN):
        _, label, name, origin = next(f for f in FIRES if f[0] == fid)
        p = perims[name]
        f = d[d.fire == fid]
        start = pd.Timestamp(REPORTED[fid][0]) - PST
        first = f.groupby(["lat", "lon"]).time.min().reset_index()
        first["h"] = (first.time.dt.tz_localize(None) - start) / pd.Timedelta("1h")
        first["bin"] = pd.cut(first.h.clip(lower=0), BINS, right=False, labels=False)
        first = first.sort_values("h", ascending=False)  # earliest drawn last, on top
        polys = footprints(first.lat.values, first.lon.values)
        w, s, e, n = p["geom"].bounds
        if len(polys):
            w, e = min(w, polys[..., 0].min()), max(e, polys[..., 0].max())
            s, n = min(s, polys[..., 1].min()), max(n, polys[..., 1].max())
        k = np.cos(np.radians((s + n) / 2))
        half = max((e - w) * k, n - s) / 2 + 0.012
        cx, cy = (w + e) / 2, (s + n) / 2
        draw_base(ax, land, (cx - half / k, cx + half / k, cy - half, cy + half))
        ax.add_collection(PolyCollection(polys, facecolors=[BLUES[int(b)] for b in first.bin],
                                         edgecolors=SURFACE, linewidths=0.5, zorder=3))
        draw_outline(ax, p["geom"])
        draw_origin(ax, *origin)
        scale_bar(ax, 5, cy)
        t = pd.Timestamp(REPORTED[fid][0])
        ax.set_title(label, pad=22, fontsize=11)
        ax.text(0, 1.015, f"Started {t:%b %-d}, {clock(t)} · {len(first)} pixels · {p['acres']:,.0f} acres",
                transform=ax.transAxes, fontsize=8.5, color=INK2, va="bottom")
    handles = [Patch(color=c, label=l) for c, l in zip(BLUES, BIN_LABELS)]
    handles += [Line2D([], [], color=INK, lw=0.9, label="Final perimeter"),
                Line2D([], [], ls="", marker="o", ms=7, mfc=SURFACE, mec=INK, mew=1.4, label="Reported origin")]
    fig.legend(handles=handles, loc="lower left", ncol=6, bbox_to_anchor=(0.01, 0.02), handlelength=1.2,
               columnspacing=1.4, title="When the satellite first saw each pixel, after the reported start",
               title_fontsize=8.5, alignment="left")
    title_block(fig, "How each fire grew, pixel by pixel",
                "Darker tiles were burning earliest. Each map is scaled to fit its fire; see the 5 km bars.", y=0.985)
    save(fig, "la_02_spread_maps.png")


def fig_power_timeline(d, scans):
    """Hourly power for the three big fires, then how quickly each released its energy."""
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(10, 7.8), gridspec_kw=dict(hspace=0.5, height_ratios=[1.25, 1]))
    fig.subplots_adjust(top=0.81)
    peak_label = {}
    for fid in MAIN:
        s = rate(d[d.fire == fid], scans, "h").frp_filled
        ax.plot(s.index + pd.Timedelta("30min"), s.fillna(0), color=COLOR[fid], lw=1.2)
        i = s.idxmax()
        peak_label[fid] = f"{LABEL[fid]}, peak {s.max():.0f} GW ({i:%b %-d})"
        # Name each burst above a peak that no other line crosses. Eaton's first peak sits under the
        # Palisades line, so it is named at its second burst on Jan 9.
        if fid == "eaton":
            i = s.loc["2025-01-09 06:00":"2025-01-09 18:00"].idxmax()
        ax.annotate(LABEL[fid], (i + pd.Timedelta("30min"), s.loc[i]), xytext=(0, 5), textcoords="offset points",
                    fontsize=8.5, color=INK, ha="center", va="bottom", fontweight="bold")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.1)
    top = ax.get_ylim()[1]
    for t, text, y in ((RAIN, "First rain", 0.62), (CONTAINED, "Palisades and Eaton\n100% contained", 0.4)):
        ax.axvline(t, color=INK2, lw=0.7, zorder=1)
        ax.text(t, top * y, text + " ", fontsize=7.5, color=INK2, va="top", ha="right")
    ax.set_xlim(START, END)
    ax.set_ylim(0, top)
    ax.xaxis.set_major_locator(mdates.DayLocator(bymonthday=[7, 10, 13, 16, 19, 22, 25, 28, 31]))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %-d"))
    ax.set_ylabel("GW, hourly average")
    ax.set_title("Fire radiative power", pad=26)
    ax.legend(handles=[Line2D([], [], color=COLOR[f], lw=1.6, label=peak_label[f]) for f in MAIN],
              loc="lower left", ncol=3, bbox_to_anchor=(0, 1.0), borderaxespad=0.2)

    day1 = {}
    for fid in MAIN:
        start = pd.Timestamp(REPORTED[fid][0]).floor("h")
        s = rate(d[d.fire == fid], scans, "h").frp_filled.fillna(0).loc[start:]
        cum = s.cumsum() / s.sum() * 100
        days = (cum.index - start) / pd.Timedelta("1D")
        bx.plot(days, cum.values, color=COLOR[fid], lw=1.8)
        day1[fid] = cum.iloc[min(24, len(cum) - 1)]
        bx.plot(1, day1[fid], "o", ms=6, color=COLOR[fid], mec=SURFACE, mew=1.2, zorder=4)
    bx.axvline(1, color=INK2, lw=0.7, zorder=1)
    bx.text(1, 2, " end of day 1", fontsize=7.5, color=INK2, va="bottom")
    # The day-1 shares go in the legend: the curves cross near day 1, so labels there would collide.
    bx.legend(handles=[Line2D([], [], color=COLOR[f], lw=1.8, marker="o", ms=5, label=f"{LABEL[f]}: {day1[f]:.0f}% by end of day 1")
                       for f in MAIN], loc="lower right")
    bx.set_xlim(0, 6)
    bx.set_ylim(0, 100)
    bx.set_yticks([0, 25, 50, 75, 100])
    bx.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:.0f}%"))
    bx.set_xlabel("Days after the reported start")
    bx.set_title("Share of each fire's total energy released so far", pad=14)
    title_block(fig, "The fires released most of their energy in the first day",
                "GOES-18, January 7 to 31, 2025, Pacific Standard Time", y=0.97)
    footnote(fig, "Each hour is the average of its 5-minute scans, because power is a rate. Pixels flagged as cloud or "
                  f"smoke have no power value; they get the local average ({d.frp_mw.isna().mean():.0%} of pixels here). "
                  "Energy = hourly power x 3,600 s.", y=0.03)
    save(fig, "la_03_power_timeline.png")


def fig_first_days(d, scans, g16):
    """Palisades and Eaton through the first 48 hours, and a second satellite as a check."""
    t0, t1 = pd.Timestamp("2025-01-07 08:00"), pd.Timestamp("2025-01-09 08:00")
    rows = 2 if g16 is not None else 1
    fig, axes = plt.subplots(rows, 1, figsize=(10, 3.3 * rows + 1.0), sharex=True,
                             gridspec_kw=dict(hspace=0.3, height_ratios=[1.3, 1][:rows]))
    fig.subplots_adjust(top=0.86)
    axes = np.atleast_1d(axes)
    ax = axes[0]
    shade_nights(ax, t0, t1)
    peaks = {}
    for fid in ("palisades", "eaton"):
        s = rate(d[d.fire == fid], scans, "30min", t0, t1).frp_filled
        ax.plot(s.index + pd.Timedelta("15min"), s, color=COLOR[fid], lw=1.8)
        peaks[fid] = s
    p = peaks["palisades"]
    ax.annotate(f"Palisades, peak {p.max():.0f} GW", (p.idxmax() + pd.Timedelta("15min"), p.max()), xytext=(7, 2),
                textcoords="offset points", fontsize=8.5, color=INK, fontweight="bold", va="bottom")
    # Eaton's label sits in the open space under its first-night plateau, clear of the Palisades line.
    e = peaks["eaton"]
    ax.text(pd.Timestamp("2025-01-07 19:30"), 1.2, f"Eaton, peak {e.max():.0f} GW", fontsize=8.5, color=INK,
            fontweight="bold", va="bottom")
    ax.set_ylim(0, ax.get_ylim()[1] * 1.15)
    top = ax.get_ylim()[1]
    for i, fid in enumerate(("palisades", "eaton")):
        t = pd.Timestamp(REPORTED[fid][0])
        ax.axvline(t, color=INK2, lw=0.7, zorder=1)
        ax.text(t, top * (1 - 0.08 * i), f" {LABEL[fid]} reported {clock(t)}", fontsize=7.5, color=INK2, va="top")
    ax.set_ylabel("GW")
    ax.set_title("Fire radiative power, 30-minute averages", pad=6)
    handles = [Line2D([], [], color=COLOR[f], lw=1.8, label=LABEL[f]) for f in ("palisades", "eaton")]
    handles.append(Patch(color=NIGHT, label="Night"))
    ax.legend(handles=handles, loc="upper right", ncol=3, bbox_to_anchor=(1, 1.13))
    if g16 is not None:
        bx = axes[1]
        shade_nights(bx, t0, t1)
        for label, s, color in (("GOES-18, west of LA", g16["g18"], INK), ("GOES-16, east of LA", g16["g16"], MUTED)):
            bx.plot(s.index + pd.Timedelta("15min"), s.values, color=color, lw=1.6, label=label)
        bx.set_ylim(bottom=0)
        bx.set_ylabel("GW")
        bx.set_title("Same check with a second satellite: all fires in the area, reported power only", pad=6)
        bx.legend(loc="upper right", ncol=2)
    axes[-1].xaxis.set_major_locator(mdates.HourLocator(byhour=[0, 6, 12, 18]))
    axes[-1].xaxis.set_major_formatter(FuncFormatter(
        lambda v, _: f"{clock(mdates.num2date(v).replace(tzinfo=None))}\n{mdates.num2date(v):%b %-d}"))
    axes[-1].set_xlim(t0, t1)
    title_block(fig, "The first 48 hours: both fires peaked after dark, then dropped before dawn",
                "Palisades and Eaton, January 7 to 9, 2025, Pacific Standard Time", y=0.975)
    footnote(fig, "Both satellites show the drop between about 4 and 7 a.m. on Jan 8, so it is not one sensor's glitch. "
                  "They run the same detection algorithm, so this data alone cannot say whether the fire, thick smoke, "
                  "or the algorithm caused it. GOES-16 sees LA at a steeper angle, so its pixels are larger.", y=0.02)
    save(fig, "la_04_first_48_hours.png")


def fig_spread_distance(d, perims):
    fig, ax = plt.subplots(figsize=(9.5, 5.0))
    fig.subplots_adjust(top=0.82)
    out = {}
    for fid in MAIN:
        _, label, name, _ = next(f for f in FIRES if f[0] == fid)
        p = dict(perims[name], discovered=pd.Timestamp(REPORTED[fid][0]).tz_localize("UTC") - PST)
        pts, unlinked = bf.spread(d[d.fire == fid], p)
        out[fid] = (pts, unlinked)
        h = [0] + [q[0] for q in pts] + [72]
        km = [0] + [q[1] for q in pts]
        km = km + [km[-1]]
        ax.step(h, km, where="post", color=COLOR[fid], lw=1.8)
        ax.text(72.8, km[-1], f"{label}  {km[-1]:.0f} km", color=INK, fontsize=9, va="center", fontweight="bold")
    ax.set_xlim(0, 72)
    ax.set_xticks(range(0, 73, 6))
    ax.set_xlabel("Hours after the reported start")
    ax.set_ylabel("km from origin")
    ax.set_ylim(bottom=0)
    ax.legend(handles=[Line2D([], [], color=COLOR[f], lw=1.8, label=LABEL[f]) for f in MAIN], loc="lower right")
    title_block(fig, "How far each fire reached from where it started",
                "Farthest pixel connected to the origin, first 72 hours", y=0.97)
    footnote(fig, "A pixel counts once it lies within 6 km of the footprint already connected to the origin, so separate "
                  "spot fires only count when they link up. Distances are pixel centres, so the first step already "
                  "sits a few km out (7 km for Hughes, which ran before its first scans), and steps under ~3 km are "
                  "within one pixel.", y=0.0)
    save(fig, "la_05_spread_distance.png")
    return out


def fig_energy(stats):
    s = stats.sort_values("energy_tj")
    fig, axes = plt.subplots(1, 2, figsize=(10, 0.42 * len(s) + 1.5), sharey=True, gridspec_kw=dict(wspace=0.1))
    fig.subplots_adjust(top=0.78)
    y = np.arange(len(s))
    colors = [COLOR.get(f, COLOR["other"]) for f in s.index]
    for ax, col, title in ((axes[0], "energy_tj", "Total fire radiative energy, TJ"),
                           (axes[1], "mj_per_acre", "Energy per burned acre, MJ")):
        ax.barh(y, s[col], color=colors, height=0.55)
        for yi, v in zip(y, s[col]):
            ax.text(v, yi, f"  {v:,.1f}" if v < 10 else f"  {v:,.0f}", va="center", fontsize=8.5, color=INK)
        ax.set_title(title, pad=6, fontsize=9.5)
        ax.grid(axis="x")
        ax.grid(axis="y", visible=False)
        ax.set_xlim(0, s[col].max() * 1.22)
        ax.xaxis.set_major_formatter(THOUSANDS)
        ax.tick_params(axis="x", labelsize=8)
    axes[0].set_yticks(y, [LABEL[f] for f in s.index])
    title_block(fig, "How much energy each fire released, January 7 to 31",
                "Fires with an official perimeter", y=0.99)
    footnote(fig, "Energy = hourly average power x 3,600 s, summed. Acres are NIFC final perimeters. A pixel only "
                  "records fire hot enough to detect, so small or brief fires are measured less reliably.", y=-0.03)
    save(fig, "la_06_energy.png")


def fig_latency(stats):
    s = stats.dropna(subset=["first_seen_min"]).sort_values("reported_earliest", ascending=False)
    fig, ax = plt.subplots(figsize=(9, 0.48 * len(s) + 1.9))
    fig.subplots_adjust(top=0.78)
    y = np.arange(len(s))
    ax.axvline(0, color=INK2, lw=0.8)
    for yi, (fid, r) in zip(y, s.iterrows()):
        span = (r.reported_latest - r.reported_earliest) / pd.Timedelta("1min")
        if span > 0:
            ax.plot([0, span], [yi, yi], color="#b9b8b2", lw=6, solid_capstyle="round", zorder=1)
        else:
            ax.plot(0, yi, "|", ms=12, mew=2, color="#b9b8b2", zorder=1)
        c = COLOR.get(fid, COLOR["other"])
        ax.plot(r.first_seen_min, yi, "o", ms=8, color=c, mec=SURFACE, mew=1.5, zorder=3)
        inside = 0 < r.first_seen_min < span
        ax.annotate(f"{r.first_seen_min:+.0f} min", (r.first_seen_min, yi), xytext=(5, 9) if inside else (8, 0),
                    textcoords="offset points", ha="left",
                    va="bottom" if inside else "center", fontsize=8, color=INK)
    ax.set_yticks(y, [f"{LABEL[f]}  ({pd.Timestamp(r.reported_earliest):%b %-d})" for f, r in s.iterrows()])
    ax.set_ylim(-0.7, len(s) - 0.3)
    ax.grid(axis="x")
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Minutes after the earliest reported start")
    lo = min(-5, s.first_seen_min.min() - 5)
    hi = max(70, s.first_seen_min.max() + 10)
    ax.set_xlim(lo, hi)
    handles = [Line2D([], [], color="#b9b8b2", lw=6, label="Reported start, range across sources"),
               Line2D([], [], ls="", marker="o", ms=7, color=COLOR["other"], label="First GOES-18 scan with the fire")]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2)
    title_block(fig, "How soon the satellite saw each fire",
                "Minutes from the earliest reported start to the first scan that caught it", y=0.99)
    footnote(fig, "Scan time is the start of the 5-minute scan; the processed file arrives a few minutes later. "
                  "A pixel needs to fire twice within 2 hours to count. Reported times: NIFC, CAL FIRE, LAFD and news "
                  "reports (README), which disagree for Kenneth, Hurst and Hughes.", y=0.0)
    save(fig, "la_07_detection_time.png")


# ---------------------------------------------------------------- summary and main

def fire_stats(d, scans, perims, spreads):
    rows = []
    for fid in [f for f, *_ in FIRES] + list(POINT_FIRES):
        f = d[d.fire == fid]
        if f.empty:
            continue
        name = next((n for x, _, n, _ in FIRES if x == fid), None)
        acres = perims[name]["acres"] if name in perims else np.nan
        early, late = (pd.Timestamp(t) for t in REPORTED.get(fid, (None, None))) if fid in REPORTED else (pd.NaT, pd.NaT)
        hourly = rate(f, scans, "h").frp_filled
        e = energy_tj(hourly)
        first = f.pst.min()
        day1 = energy_tj(hourly.loc[early.floor("h"):early.floor("h") + pd.Timedelta("23h")]) if pd.notna(early) else np.nan
        dark = sun_elevation(f.time.dt.tz_localize(None), f.lat.values, f.lon.values) < 0
        pts = spreads.get(fid, ([], 0))[0]
        rows.append(dict(
            fire=fid, name=LABEL[fid], acres=round(acres) if pd.notna(acres) else np.nan,
            reported_earliest=early, reported_latest=late, first_seen=first,
            first_seen_min=round((first - early) / pd.Timedelta("1min")) if pd.notna(early) else np.nan,
            last_seen=f.pst.max(), pixel_detections=len(f), unique_pixels=f.groupby(["lat", "lon"]).ngroups,
            peak_gw=round(hourly.max(), 1), peak_hour=hourly.idxmax(),
            energy_tj=round(e, 1), share_first_24h=round(day1 / e, 3) if e else np.nan,
            share_energy_after_dark=round(float((f.frp_filled * dark).sum() / f.frp_filled.sum()), 3),
            mj_per_acre=round(e * 1e6 / acres) if pd.notna(acres) else np.nan,
            no_power_share=round(f.frp_mw.isna().mean(), 3),
            farthest_km=pts[-1][1] if pts else np.nan))
    return pd.DataFrame(rows).set_index("fire")


def goes16_check(d18, scans18):
    """Reported power over the whole area, both satellites, 30-minute averages, first 48 hours."""
    path = DATA / "la_2025_goes16_first48h.csv"
    if not path.exists():
        return None
    t0, t1 = pd.Timestamp("2025-01-07 08:00"), pd.Timestamp("2025-01-09 08:00")
    g16 = bf.drop_one_off_pixels(pd.read_csv(path, parse_dates=["time"]))
    sc16 = pd.read_csv(DATA / "la_2025_goes16_first48h_scans.csv", parse_dates=["time"])
    for frame in (g16, sc16):
        frame["pst"] = (frame.time + PST).dt.tz_localize(None)
    return {"g18": rate(d18[["pst", "frp_mw"]], scans18, "30min", t0, t1).frp_mw,
            "g16": rate(g16[["pst", "frp_mw"]], sc16, "30min", t0, t1).frp_mw}


def main():
    d, scans, perims, n_raw = load()
    land = shape(json.load(open(DATA / "land_la.geojson"))["features"][0]["geometry"])
    print(f"{len(scans):,} scans, {n_raw:,} raw pixels, {len(d):,} kept after the persistence filter")
    print(d.fire.value_counts().to_string())
    print("pixel size km at Palisades:", [round(v, 2) for v in pixel_km(34.07, -118.55)])

    fig_overview(d, perims, land)
    fig_spread_maps(d, perims, land)
    fig_power_timeline(d, scans)
    g16 = goes16_check(d, scans)
    fig_first_days(d, scans, g16)
    spreads = fig_spread_distance(d, perims)
    stats = fire_stats(d, scans, perims, spreads)
    fig_energy(stats.dropna(subset=["acres"]))
    fig_latency(stats)
    stats.to_csv(HERE / "la_2025_summary.csv")
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(stats.T.to_string())
    if g16 is not None:
        both = pd.DataFrame(g16).dropna()
        print("GOES-16 vs GOES-18 30-min power, correlation:", round(both.g16.corr(both.g18), 3),
              " totals ratio g16/g18:", round(both.g16.sum() / both.g18.sum(), 2))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Build data/la_fires.json, the single file the web page loads.

It reuses the processing in visualizations/static/la_fires_2025.py (persistence filter,
gap fill, attribution to fires, pixel footprints), so every number on the page matches
the static figures and visualizations/static/la_2025_summary.csv.

Inputs
  visualizations/static/data/*                 GOES-18/16 detections, perimeters, coastline
  visualizations/static/data/summer_west_2026_by_hour.csv
      Share of fire radiative power by solar hour, western US, Jul 13 to Aug 31, 2026
      (the Project 3 data). Rebuilt from Project 3's data/fires.json when --summer points to it.

Usage
  python scripts/build_web_data.py [--summer ../dsc106-project-3/data/fires.json]

Times in the output are Pacific Standard Time (UTC-8), written as "YYYY-MM-DDTHH:MM".
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "visualizations" / "static"
sys.path.insert(0, str(STATIC))
import la_fires_2025 as m  # noqa: E402

SUMMER_CSV = STATIC / "data" / "summer_west_2026_by_hour.csv"
STEP = "30min"
STEP_MIN = 30


def iso(t):
    return None if pd.isna(t) else pd.Timestamp(t).strftime("%Y-%m-%dT%H:%M")


def r(x, n=2):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else round(float(x), n)


def summer_profile(path):
    """Share of total power in each solar hour, from Project 3's fires.json ('All West' series)."""
    if path and Path(path).exists():
        rows = pd.DataFrame(json.load(open(path))["series"][0]["rows"],
                            columns=["idx", "with_frp", "no_frp", "raw_gw", "filled_gw"])
        by = rows.groupby(rows.idx % 24).filled_gw.sum()
        out = pd.DataFrame({"hour": range(24), "share": (by / by.sum()).reindex(range(24), fill_value=0).values})
        out.to_csv(SUMMER_CSV, index=False, float_format="%.5f")
    return pd.read_csv(SUMMER_CSV).share.tolist()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--summer", help="Project 3 data/fires.json, to rebuild the summer hour-of-day profile")
    ap.add_argument("--out", default=str(ROOT / "data" / "la_fires.json"))
    args = ap.parse_args()

    d, scans, perims, n_raw = m.load()
    stats = m.fire_stats(d, scans, perims, {})

    # ---- pixels: one entry per GOES-18 pixel, with its true footprint
    px = (d.groupby(["lat", "lon"])
            .agg(fire=("fire", lambda s: s.mode().iat[0]), first=("pst", "min"), n=("time", "size"),
                 mw=("frp_filled", "max"))
            .reset_index())
    polys = m.footprints(px.lat.values, px.lon.values)
    index = {(a, b): i for i, (a, b) in enumerate(zip(px.lat, px.lon))}
    d["pix"] = [index[k] for k in zip(d.lat, d.lon)]
    pixels = [dict(f=f, p=[[round(x, 4), round(y, 4)] for x, y in poly], first=iso(t), n=int(n), mw=r(mw, 0))
              for f, poly, t, n, mw in zip(px.fire, polys, px["first"], px.n, px.mw)]

    # ---- fires
    fires = []
    for fid, row in stats.iterrows():
        name = next((n for f, _, n, _ in m.FIRES if f == fid), None)
        origin = next((o for f, _, _, o in m.FIRES if f == fid), None)
        if fid in m.POINT_FIRES:
            origin = (m.POINT_FIRES[fid]["lat"], m.POINT_FIRES[fid]["lon"])
        fires.append(dict(
            id=fid, name=row["name"], main=fid in m.MAIN, perimeter=name in perims,
            acres=None if pd.isna(row.acres) else int(row.acres),
            origin=None if origin is None else [origin[1], origin[0]],
            reported=[iso(row.reported_earliest), iso(row.reported_latest)],
            firstSeen=iso(row.first_seen), firstSeenMin=r(row.first_seen_min, 0),
            lastSeen=iso(row.last_seen), pixels=int(row.unique_pixels),
            peakGW=r(row.peak_gw, 1), peakHour=iso(row.peak_hour),
            energyTJ=r(row.energy_tj, 1), mjPerAcre=r(row.mj_per_acre, 0),
            share24h=r(row.share_first_24h, 3), shareDark=r(row.share_energy_after_dark, 3)))

    # ---- perimeters (properties reduced to the fire id) and coastline
    geo = json.load(open(STATIC / "data" / "perimeters_la_2025.geojson"))
    by_name = {n: f for f, _, n, _ in m.FIRES}
    perimeter_features = [dict(type="Feature", properties=dict(fire=by_name[f["properties"]["poly_IncidentName"]]),
                               geometry=f["geometry"])
                          for f in geo["features"] if f["properties"]["poly_IncidentName"] in by_name]
    land = json.load(open(STATIC / "data" / "land_la.geojson"))["features"][0]["geometry"]

    # ---- first 48 hours, 30-minute power, plus the GOES-16 check over the whole area
    t0, t1 = pd.Timestamp("2025-01-07 08:00"), pd.Timestamp("2025-01-09 08:00")
    g16 = m.goes16_check(d, scans)
    first48 = dict(
        start=iso(t0), stepMin=STEP_MIN,
        palisades=[r(v) for v in m.rate(d[d.fire == "palisades"], scans, STEP, t0, t1).frp_filled],
        eaton=[r(v) for v in m.rate(d[d.fire == "eaton"], scans, STEP, t0, t1).frp_filled],
        g18=[r(v) for v in g16["g18"]], g16=[r(v) for v in g16["g16"]],
        nights=[[iso(a), iso(b)] for a, b in m.night_spans(t0, t1)])

    # ---- growth: which pixels burned in each 30-minute step after the reported start
    growth = {}
    for fid in m.MAIN:
        f = d[d.fire == fid]
        start = pd.Timestamp(m.REPORTED[fid][0]).floor(STEP)
        last = min(f.pst.max(), start + pd.Timedelta("4D"))
        steps = int(np.ceil((last - start) / pd.Timedelta(STEP))) + 1
        end = start + steps * pd.Timedelta(STEP)
        n_scans = scans.groupby(scans.pst.dt.floor(STEP)).size()
        g = f[(f.pst >= start) & (f.pst < end)].copy()
        g["k"] = ((g.pst - start) / pd.Timedelta(STEP)).astype(int)
        g["bin"] = g.pst.dt.floor(STEP)
        agg = g.groupby(["k", "pix", "bin"]).frp_filled.sum().reset_index()
        agg["mw"] = agg.frp_filled / agg.bin.map(n_scans)
        frames = [[] for _ in range(steps)]
        for k, p, mw in zip(agg.k, agg.pix, agg.mw):
            frames[k].append([int(p), int(round(mw))])
        gw = m.rate(f, scans, STEP, start, end).frp_filled
        growth[fid] = dict(start=iso(start), stepMin=STEP_MIN, frames=frames, gw=[r(v) for v in gw],
                           nights=[[iso(a), iso(b)] for a, b in m.night_spans(start, end)])

    # ---- days after the start: hourly power and cumulative share of energy (10 days)
    daily = {}
    for fid in m.MAIN:
        start = pd.Timestamp(m.REPORTED[fid][0]).floor("h")
        s = m.rate(d[d.fire == fid], scans, "h").frp_filled.fillna(0)
        total = s.sum()
        s = s.loc[start:start + pd.Timedelta(hours=239)]
        daily[fid] = dict(start=iso(start), gw=[r(v) for v in s], cum=[r(v, 1) for v in s.cumsum() / total * 100])

    # ---- when fires burn: share of power by hour of day, Palisades and Eaton together.
    # During the Santa Ana wind event (first 48 hours, 73% of their energy) the cycle flipped;
    # after the winds eased (Jan 9 to 12) it returned to the usual daytime peak.
    la = pd.concat([m.rate(d[d.fire == f], scans, "h").frp_filled.fillna(0) for f in ("palisades", "eaton")], axis=1).sum(axis=1)

    def by_hour(s):
        b = s.groupby(s.index.hour).sum()
        return [r(v, 4) for v in (b / b.sum()).reindex(range(24), fill_value=0)]

    night = m.night_spans(pd.Timestamp("2025-01-08 00:00"), pd.Timestamp("2025-01-08 23:59"))
    hour_of_day = dict(
        winds=by_hour(la.loc["2025-01-07 10:00":"2025-01-09 09:00"]),
        after=by_hour(la.loc["2025-01-09 10:00":"2025-01-12 23:00"]),
        windsShareOfEnergy=r(la.loc["2025-01-07 10:00":"2025-01-09 09:00"].sum() / la.sum(), 3),
        summer=[r(v, 4) for v in summer_profile(args.summer)],
        sunrise=r(night[0][1].hour + night[0][1].minute / 60, 2),
        sunset=r(night[-1][0].hour + night[-1][0].minute / 60, 2))

    out = dict(
        meta=dict(satellite="GOES-18", product="ABI-L2-FDCC", start=iso(m.START), end=iso(m.END),
                  bbox=[-119.3, 33.8, -117.6, 34.8], scans=int(len(scans)), rawPixels=int(n_raw),
                  keptPixels=int(len(d)), pixelKm=[r(v) for v in m.pixel_km(34.07, -118.55)],
                  noPowerShare=r(d.frp_mw.isna().mean(), 3), timezone="PST (UTC-8)"),
        fires=fires, pixels=pixels, perimeters=dict(type="FeatureCollection", features=perimeter_features),
        land=land, first48=first48, growth=growth, daily=daily, hourOfDay=hour_of_day)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    json.dump(out, open(args.out, "w"), separators=(",", ":"))
    print(f"wrote {args.out}: {Path(args.out).stat().st_size / 1024:.0f} KB, "
          f"{len(pixels)} pixels, {sum(len(fr) for g in growth.values() for fr in g['frames'])} growth entries")


if __name__ == "__main__":
    main()

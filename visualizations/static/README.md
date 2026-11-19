# January 2025 Los Angeles fires, seen from GOES

Static figures (PNG) from NOAA GOES fire detections for the Palisades, Eaton, Hughes and smaller
Los Angeles fires, January 7 to 31, 2025. This folder is separate from the web page and does not
change it.

## Figures

| File | What it shows |
|---|---|
| `la_01_overview_map.png` | Every fire pixel GOES-18 saw over the period, by fire, with official perimeters |
| `la_02_spread_maps.png` | Palisades, Eaton and Hughes: when each pixel was first seen, after the reported start |
| `la_03_power_timeline.png` | Hourly fire radiative power, and the share of each fire's energy released over time |
| `la_04_first_48_hours.png` | Palisades and Eaton through the first two days, checked against a second satellite (GOES-16) |
| `la_05_spread_distance.png` | Farthest connected pixel from each origin, first 72 hours |
| `la_06_energy.png` | Total fire radiative energy per fire, and per burned acre |
| `la_07_detection_time.png` | Minutes from the reported start to the first satellite scan that caught each fire |
| `la_2025_summary.csv` | The per-fire numbers behind the figures |

## What the data shows

| Fire | Final size | Peak power (hourly) | Total energy | Share in first 24 h | Farthest connected reach | First seen after earliest report |
|---|---|---|---|---|---|---|
| Palisades | 23,448 acres | 24 GW, Jan 7 11 p.m. | 1,809 TJ | 53% | 14 km | 1 min |
| Eaton | 14,021 acres | 9 GW, Jan 8 midnight | 524 TJ | 72% | 10 km | 16 min |
| Hughes | 10,425 acres | 14 GW, Jan 22 11 a.m. | 251 TJ | over 99% | 9 km | 6 min |

- **The satellite caught the fires within minutes.** GOES-18 flagged Palisades in the first scan
  after its reported 10:30 a.m. start. Every fire with a reported time was caught within 16
  minutes, except Auto (31 minutes). Laguna, a 67-acre fire, took 137 minutes and is left out of
  figure 7 so it does not stretch the axis.
- **Palisades and Eaton burned hardest at night.** Palisades peaked at 11 p.m. on January 7 and
  Eaton around 3 a.m. on January 8, during the Santa Ana wind event. That is the reverse of the
  usual pattern: in the summer 2026 data on the web page, fire detections peak at 3 p.m. and are
  lowest around 4 a.m. Hughes started mid-morning and made its run within hours, so it released
  almost all its energy in daylight.
- **Most of the energy came out on day one.** Eaton released 72% of its energy in its first 24
  hours, and Hughes nearly all of it within about 8 hours. Palisades released half on day one but
  kept burning at a measurable level for about four days.
- **Palisades released twice as much energy per acre as Eaton** (77,000 vs 37,000 MJ per acre).
  Part of that is its longer burn; this data cannot separate fuel, terrain and duration.
- **A sharp drop before dawn on January 8.** Power over the whole area fell from about 33 GW at
  11 p.m. to about 4 GW between 5 and 7 a.m., then rose to about 18 GW by 9 a.m. GOES-16, looking
  from the other side, shows the same drop: its half-hourly power tracks GOES-18 with a correlation
  of 0.96, and its total over the 48 hours is 96% of GOES-18's.
- **Few pixels lack a power value.** About 10% of fire pixels were flagged as cloud or smoke and
  have no power value, against 37% in the summer 2026 western data, so gap-filling changes these
  totals very little.
- **Scale.** All fires together released about 2,600 TJ of radiated energy. With the standard
  conversion of 0.368 kg of fuel burned per MJ (Wooster et al., 2005), that is roughly one million
  tonnes of vegetation and structures, a rough figure that is only good to a factor of about 2.

## Data

| Item | Value |
|---|---|
| Satellite | GOES-18 (GOES-West, 137.0°W), bucket `noaa-goes18` |
| Product | `ABI-L2-FDCC`, Fire/Hot Spot Characterization, CONUS sector, one scan every 5 minutes |
| Period | 2025-01-07 00:00 to 2025-02-01 00:00 PST (08:00 UTC to 08:00 UTC) |
| Scans | 7,147 of 7,200 possible. The archive is missing 3 hours on Jan 16 and 1.5 hours on Jan 27, both with no fire |
| Pixels | 14,047 fire pixels, 14,016 after the persistence filter |
| Area | 119.3°W to 117.6°W, 33.8°N to 34.8°N (Los Angeles and eastern Ventura counties) |
| Check | GOES-16 (GOES-East, 75.2°W at the time) `ABI-L2-FDCC`, Jan 7 08:00 to Jan 9 10:00 PST only |
| Perimeters | NIFC WFIGS Interagency Perimeters and Incident Locations (origins, discovery times) |
| Coastline | Natural Earth 10 m land, v5.1.2, clipped to the area |

Variables used from each GOES file: `Mask` (fire category), `Power` (fire radiative power, MW),
`x`/`y` with `goes_imager_projection` (converted to lat/lon), and the scan start time from the
file name. `Temp`, `Area` and `DQF` are saved in the CSV but not used in the figures.

GOES-18 sees Los Angeles at a gentler angle than GOES-16, so its pixels are smaller here (about
2.3 by 2.8 km) and it is the main source. GOES-16 is used only to check the first two days.

Files in `data/`:

| File | Size | What it is |
|---|---|---|
| `la_2025.csv` | 842 KB | GOES-18 fire pixels: time, lat, lon, frp_mw, temp_k, area_m2, mask, dqf |
| `la_2025_scans.csv` | 161 KB | Every GOES-18 scan read, with its fire-pixel count (gaps show up here) |
| `la_2025_goes16_first48h*.csv` | 361 KB | The same for GOES-16, first two days |
| `perimeters_la_2025.geojson` | 69 KB | NIFC final perimeters, simplified to about 30 m |
| `land_la.geojson` | 4 KB | Coastline for the maps |

## Rebuild

From the repository root, with the environment from the main README
(`pip install -r requirements.txt`, plus `matplotlib`):

```bash
# 1. GOES-18 fire pixels over LA, 25 days (about 7,200 files streamed from S3, nothing saved but the CSV)
python scripts/extract_fdc.py --sat 18 --product ABI-L2-FDCC \
  --start 2025-01-07T08 --end 2025-02-01T08 --bbox -119.3 33.8 -117.6 34.8 \
  --out visualizations/static/data/la_2025

# 2. GOES-16, first two days only, as a check
python scripts/extract_fdc.py --sat 16 --product ABI-L2-FDCC \
  --start 2025-01-07T16 --end 2025-01-09T18 --bbox -119.3 33.8 -117.6 34.8 \
  --out visualizations/static/data/la_2025_goes16_first48h

# 3. Figures and summary
python visualizations/static/la_fires_2025.py
```

The perimeters came from the NIFC ArcGIS service `WFIGS_Interagency_Perimeters` (query:
California, discovered January 6 to 31, 2025, over 50 acres, Los Angeles or Ventura county), and
the origins from `WFIGS_Incident_Locations`, both at
<https://data-nifc.opendata.arcgis.com/>.

## Method

The processing reuses the web page's functions in `scripts/build_fires.py`, so the numbers mean
the same thing. In order:

1. **Persistence.** A pixel counts only if the same pixel is flagged again within 2 hours. One-off
   hits are mostly false alarms.
2. **Missing power.** Pixels flagged as cloud or smoke have no power value; each gets the mean
   power of valid pixels in the same half-degree cell and hour. Only about 10% of pixels here lack
   a power value (in the summer western data it was 37%), so this changes little.
3. **Power is a rate.** Every hourly or 30-minute value is the average over the scans in that bin,
   not the sum. Energy is hourly power times 3,600 seconds.
4. **Attribution.** A pixel belongs to the nearest fire whose final perimeter lies within 5 km.
   Two fires have no NIFC perimeter, so pixels near their reported location and time are assigned
   by distance instead: Lidia (within 6 km of the NIFC incident point) and Sunset (within 4 km of
   Runyon Canyon, the evening of January 8, from news reports). These are labelled as such.
5. **Spread.** Distance from the reported origin to the farthest pixel connected to it (within
   6 km of the footprint grown so far), so a separate start inside the final perimeter only counts
   once it links up.
6. **Time.** Pacific Standard Time (UTC-8), because the reported start times are local clock times.
   The web page uses solar time instead; at Los Angeles the two differ by under 10 minutes.
7. **Night.** Sun below the horizon at the fire, from a standard solar-position formula.

## Limits

- A GOES pixel covers about 6 km². Palisades (95 km²) is about 35 pixels, so the maps show the
  shape of each fire but not street-level detail, and distances move in steps of 2 to 3 km.
- Fire radiative power is the heat radiated, not the total heat, and smoke can hide part of it.
  Comparisons between fires are safer than the absolute numbers.
- The drop in power before dawn on January 8 appears in both satellites, but both use the same
  detection algorithm, so this data cannot say whether the fire, smoke or the algorithm caused it.
- Reported start times disagree between sources for Kenneth, Hurst and Hughes, so figure 7 shows
  a range.
- `scripts/extract_fdc.py` needed a small fix for this data: some 2025 files store `Mask` or `DQF`
  as unsigned 8-bit, which cannot hold the -1 used for missing values. The fix casts first; it does
  not change the web page's data.

## Sources for events and times

| Fire or event | Time used (PST) | Sources |
|---|---|---|
| Palisades start | Jan 7, 10:30 a.m. | NIFC; [The Lookout](https://the-lookout.org/2025/01/08/january-2025-southern-california-fires-day-2/) |
| Eaton start | Jan 7, 6:15 to 6:19 p.m. | NIFC (6:18:47 p.m.); [CAL FIRE](https://fire.ca.gov/incidents/2025/1/7/eaton-fire); news reports (about 6:15 p.m.) |
| Hurst start | Jan 7, 10:10 to 10:30 p.m. | [NBC Los Angeles](https://www.nbclosangeles.com/news/local/san-fernando-valley-sylmar-brush-fire/3597251/?noamp=mobile) and [SCE report to CPUC](https://www.cpuc.ca.gov/-/media/cpuc-website/divisions/safety-and-enforcement-division/electric-safety-incidents-reported-by-ious/2025-incidents/2025-1-10-eir.pdf) (10:10 p.m.); NIFC (10:30 p.m.); [CAL FIRE](https://www.fire.ca.gov/incidents/2025/1/7/hurst-fire) (10:29 p.m.) |
| Lidia start | Jan 8, 12:59 p.m. | NIFC incident location |
| Sunset start and size | Jan 8, about 5:30 p.m.; about 43 acres | [CBS News](https://www.cbsnews.com/news/hollywood-hills-fire-sunset-los-angeles/), [Patch](https://patch.com/california/hollywood/sunset-fire-evacuation-orders-lifted-hollywood-hills) |
| Kenneth start | Jan 9, 2:30 to 3:34 p.m. | News reports (about 2:30 p.m.), NIFC (2:52 p.m.), [CAL FIRE](https://www.fire.ca.gov/incidents/2025/1/9/kenneth-fire) (3:34 p.m.) |
| Auto start | Jan 13, 6:50 p.m. | NIFC |
| Hughes start | Jan 22, 10:30 to 10:53 a.m. | [NBC Los Angeles](https://www.nbclosangeles.com/news/local/la-wildfire-hughes-fire-castaic-5-freeway/3612218/?amp=1) and [ABC7](https://abc7.com/live-updates/strong-winds-return-southern-california-crews-high-alert/15820447/entry/15826530) (about 10:30 a.m.); NIFC (10:37 a.m.); [CAL FIRE](https://www.fire.ca.gov/incidents/2025/1/22/hughes-fire) (10:53 a.m.) |
| First rain | Jan 26 | [Fox Weather](https://foxweather.com/weather-news/los-angeles-wildfire-burn-scars-flood-watch-rain) |
| Palisades and Eaton 100% contained | Jan 31 | [Fox LA](https://www.foxla.com/news/eaton-fire-reaches-100-containment-after-3-weeks), [CAL FIRE](https://fire.ca.gov/incidents/2025/1/7/eaton-fire) |

Energy-to-fuel conversion: Wooster, M. J., Roberts, G., Perry, G. L. W., and Kaufman, Y. J.
(2005), "Retrieval of biomass combustion rates and totals from fire radiative power
observations", *Journal of Geophysical Research*, 110, D24311.

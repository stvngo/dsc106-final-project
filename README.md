# Fire After Dark

DSC 106 final project: an explorable explanation of the January 2025 Los Angeles fires
(Palisades, Eaton, Hughes and smaller fires), seen by the GOES-18 weather satellite every 5 minutes.
This is the **initial prototype**: the story structure, D3 versions of the main charts, their first
interactions, and short descriptive text.

## View it

The page loads a JSON file, so it needs a web server (opening `index.html` directly will not work):

```bash
python3 -m http.server 8000
# open http://localhost:8000
```

VS Code Live Server also works. For GitHub Pages, publish from the repository root; `index.html`,
`css/`, `js/` and `data/` are all at the top level. D3 v7 is the only library and loads from a CDN.

## What is on the page

| Section | Chart | Interaction |
|---|---|---|
| 1 | Map of every GOES-18 fire pixel, with official perimeters | Hover a pixel; click a legend entry to pick out a fire |
| 2 | Minutes from each fire's reported start to its first satellite scan | Hover a row |
| 3 | Share of fire power by hour of day: summer 2026 western fires vs Palisades + Eaton | Guess the peak hour first, then compare; toggle the wind days and the days after |
| 4 | Power every 30 minutes for the first 48 hours | Hover crosshair; toggle a GOES-18 vs GOES-16 check |
| 5 | Replay of each fire's growth, pixel by pixel | Play, slider, click the power strip to jump; choose the fire |
| 6 | Energy released over each fire's first 10 days | Hover crosshair; toggle share of energy vs power |
| 7 | Total and per-acre fire radiative energy | Toggle the measure; hover a bar |

## Files

```
index.html                  the page
css/style.css               styles, light and dark themes
js/main.js                  all D3 code, one function per section
data/la_fires.json          everything the page loads (built by scripts/build_web_data.py)
scripts/
  extract_fdc.py            stream GOES fire files from AWS S3 and keep fire pixels (from Project 3)
  build_fires.py            shared processing functions (from Project 3)
  build_web_data.py         detections -> data/la_fires.json
visualizations/static/      static analysis: data, figure script, 7 PNG figures, summary table
  README.md                 data access, method, findings, limits and sources
PROPOSAL.md                 the project proposal
```

## Rebuild the data

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install netCDF4==1.7.4 numpy pandas s3fs shapely matplotlib

# 1-2. Extract GOES-18 and GOES-16 fire pixels (commands in visualizations/static/README.md)
# 3. Static figures
python visualizations/static/la_fires_2025.py
# 4. Page data. --summer rebuilds the summer 2026 hour-of-day profile from Project 3's data;
#    without it, the saved copy in visualizations/static/data/ is used.
python scripts/build_web_data.py --summer ../dsc106-project-3/data/fires.json
```

## Data

- NOAA GOES-18 and GOES-16 `ABI-L2-FDCC` (Fire/Hot Spot Characterization), AWS Open Data
  buckets `noaa-goes18` and `noaa-goes16`.
- NIFC WFIGS interagency fire perimeters and incident locations.
- Summer 2026 western US fire data from our Project 3 (same product), for the usual daily cycle.
- Natural Earth 10 m land.

Times are Pacific Standard Time. Method, limits and sources are in
[visualizations/static/README.md](visualizations/static/README.md).

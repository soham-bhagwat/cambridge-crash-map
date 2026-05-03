# Cambridge Crash Map

Interactive heatmap of vehicle crashes in Cambridge, MA, built from the [Cambridge Police Department crash log](https://data.cambridgema.gov/Public-Safety/Cambridge-Police-Department-Crash-Log/h6fp-bp8s).

**Live map → [soham-bhagwat.github.io/cambridge-crash-map](https://soham-bhagwat.github.io/cambridge-crash-map/)**

![Map preview showing crash density across Cambridge intersections](https://github.com/soham-bhagwat/cambridge-crash-map/raw/gh-pages/index.html)

---

## What it shows

- **Circle markers** at every intersection with 3+ recorded crashes
- **Circle size** scales with crash count
- **Color** reflects severity:
  - 🔴 Dark red — 5+ hospitalizations
  - 🟠 Orange — 2–4 hospitalizations
  - 🟡 Yellow — 1 hospitalization
  - 🟢 Teal — no hospitalizations
- **Heatmap layer** shows overall crash density
- Click any circle for crash count, injuries, and hospitalizations

## How it works

1. Pulls the latest crash CSV from the Cambridge open data portal
2. Aggregates crashes by intersection (normalizing street name variants)
3. Resolves intersection coordinates from the OpenStreetMap road network via `osmnx`
4. Renders an interactive map with `folium` and deploys to GitHub Pages

## Data

Source: Cambridge Police Department via [Analyze Boston](https://data.cambridgema.gov)  
Updated: daily at 8 AM UTC via GitHub Actions

## Run locally

```bash
pip install -r requirements.txt
python cambridge_crash_map.py
open cambridge_crashes_map.html
```

The OSM road network is cached to `cambridge_graph.graphml` after the first run.

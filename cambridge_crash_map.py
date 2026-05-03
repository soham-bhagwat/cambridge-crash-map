import pandas as pd
import folium
from folium.plugins import HeatMap
import requests
from io import StringIO

URL = "https://data.cambridgema.gov/api/views/h6fp-bp8s/rows.csv?accessType=DOWNLOAD&api_foundry=true"

print("Downloading crash data...")
headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
r = requests.get(URL, headers=headers, timeout=60)
r.raise_for_status()
df = pd.read_csv(StringIO(r.text))

print(f"Loaded {len(df)} records")

# --- Geocode using intersection or address street name ---
# We'll use a pre-built lookup of Cambridge street intersections to lat/lon
# Since the data has no lat/lon, we approximate using neighborhood centroids

neighborhood_coords = {
    "East Cambridge":       (42.3676, -71.0920),
    "Wellington-Harrington":(42.3726, -71.0850),
    "The Port":             (42.3628, -71.0939),
    "Cambridgeport":        (42.3628, -71.1083),
    "Mid-Cambridge":        (42.3740, -71.1150),
    "Riverside":            (42.3578, -71.1200),
    "West Cambridge":       (42.3810, -71.1390),
    "North Cambridge":      (42.3956, -71.1300),
    "Neighborhood Nine":    (42.3800, -71.1250),
    "Baldwin":              (42.3780, -71.1050),
    "Area 2/MIT":           (42.3593, -71.0936),
    "Cambridge Highlands":  (42.3955, -71.1490),
    "Strawberry Hill":      (42.3876, -71.1500),
    "Agassiz":              (42.3840, -71.1230),
}

import random

def jitter(lat, lon, amount=0.002):
    return lat + random.uniform(-amount, amount), lon + random.uniform(-amount, amount)

# Filter rows with known neighborhood
col = "Neighborhood (estimated)"
df[col] = df[col].astype(str).str.strip()
mapped = df[df[col].isin(neighborhood_coords)].copy()
print(f"Rows with known neighborhood: {len(mapped)}")

# Build map centered on Cambridge
m = folium.Map(location=[42.3736, -71.1097], zoom_start=13, tiles="CartoDB positron")

# Heatmap layer
heat_data = []
for _, row in mapped.iterrows():
    lat, lon = neighborhood_coords[row[col]]
    lat, lon = jitter(lat, lon, 0.003)
    heat_data.append([lat, lon])

HeatMap(heat_data, radius=12, blur=15, min_opacity=0.4).add_to(m)

# Injury markers (only hospitalized)
hosp = mapped[mapped["Hospitalizations (estimated)"].fillna(0).astype(str).str.strip().replace('',0).apply(lambda x: float(str(x).replace(',','')) if str(x).strip() else 0) > 0]
print(f"Hospitalization incidents: {len(hosp)}")

for _, row in hosp.iterrows():
    lat, lon = neighborhood_coords[row[col]]
    lat, lon = jitter(lat, lon, 0.003)
    folium.CircleMarker(
        location=[lat, lon],
        radius=5,
        color="#A32D2D",
        fill=True,
        fill_color="#E24B4A",
        fill_opacity=0.7,
        popup=f"Hospitalization | {row.get('Date Time','')} | {row[col]}",
        tooltip="Hospitalization"
    ).add_to(m)

# Legend HTML
legend_html = """
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
     padding:14px 18px;border-radius:10px;border:1px solid #ccc;font-family:sans-serif;font-size:13px;box-shadow:2px 2px 6px rgba(0,0,0,0.15);">
  <b style="font-size:14px;">Cambridge Crash Log</b><br><br>
  <span style="display:inline-block;width:16px;height:8px;background:linear-gradient(to right,#ffffb2,#fd8d3c,#bd0026);border-radius:2px;vertical-align:middle;margin-right:6px;"></span>Crash density (heatmap)<br><br>
  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#E24B4A;vertical-align:middle;margin-right:6px;"></span>Hospitalization incident
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

# Title
title_html = """
<div style="position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:1000;
     background:white;padding:10px 22px;border-radius:8px;border:1px solid #ddd;
     font-family:sans-serif;font-size:15px;font-weight:600;box-shadow:2px 2px 6px rgba(0,0,0,0.12);">
  Cambridge CPD Crash Log — All Years
</div>
"""
m.get_root().html.add_child(folium.Element(title_html))

output = "cambridge_crashes_map.html"
m.save(output)
print(f"Map saved to {output}")

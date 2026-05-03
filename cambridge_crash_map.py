import pandas as pd
import folium
from folium.plugins import HeatMap
import requests
from io import StringIO
import re, json, os
import osmnx as ox

URL = "https://data.cambridgema.gov/api/views/h6fp-bp8s/rows.csv?accessType=DOWNLOAD&api_foundry=true"
GRAPH_FILE = "cambridge_graph.graphml"
INTER_CACHE = "intersection_coords.json"

def norm(s):
    s = str(s).upper().strip().rstrip('.')
    s = re.sub(r'\bST\.?\b', 'STREET', s)
    s = re.sub(r'\bAVE?\.?\b', 'AVENUE', s)
    s = re.sub(r'\bRD\.?\b', 'ROAD', s)
    s = re.sub(r'\bBLVD\.?\b', 'BOULEVARD', s)
    s = re.sub(r'\bPKWY\.?\b', 'PARKWAY', s)
    s = re.sub(r'\bDR\.?\b', 'DRIVE', s)
    return s.strip()

def safe_float(x):
    try:
        return float(str(x).replace(",", "").strip()) if str(x).strip() not in ("", "nan") else 0.0
    except:
        return 0.0

# ── Download Cambridge road network (cached) ───────────────────────────────────
if os.path.exists(GRAPH_FILE):
    print("Loading cached road network...")
    G = ox.load_graphml(GRAPH_FILE)
else:
    print("Downloading Cambridge road network (one-time ~30s)...")
    G = ox.graph_from_place("Cambridge, Massachusetts, USA", network_type="drive")
    ox.save_graphml(G, GRAPH_FILE)
    print("Road network saved to cache.")

# Build lookup: normalized street name → list of (node_id, lat, lon)
print("Indexing streets...")
street_nodes: dict[str, list] = {}
for node_id, data in G.nodes(data=True):
    lat, lon = data["y"], data["x"]
    # collect all street names at this node
    names = set()
    for _, _, edata in G.edges(node_id, data=True):
        raw = edata.get("name", "")
        if isinstance(raw, list):
            for n in raw:
                names.add(norm(n))
        elif raw:
            names.add(norm(raw))
    for name in names:
        street_nodes.setdefault(name, []).append((node_id, lat, lon))

def find_intersection(s1, s2):
    nodes1 = {n[0] for n in street_nodes.get(s1, [])}
    nodes2 = {n[0] for n in street_nodes.get(s2, [])}
    shared = nodes1 & nodes2
    if not shared:
        return None
    # pick node closest to centroid of shared nodes
    pts = [(G.nodes[n]["y"], G.nodes[n]["x"]) for n in shared]
    lat = sum(p[0] for p in pts) / len(pts)
    lon = sum(p[1] for p in pts) / len(pts)
    return (lat, lon)

# ── Load crash data ────────────────────────────────────────────────────────────
print("Downloading crash data...")
r = requests.get(URL, headers={"User-Agent": "Mozilla/5.0"}, timeout=60)
r.raise_for_status()
df = pd.read_csv(StringIO(r.text))
print(f"Loaded {len(df)} records")

inter = df.dropna(subset=["Intersection Street One", "Intersection Street Two"]).copy()
inter["s1"] = inter["Intersection Street One"].apply(norm)
inter["s2"] = inter["Intersection Street Two"].apply(norm)
inter["key"] = inter.apply(lambda r: tuple(sorted([r["s1"], r["s2"]])), axis=1)
inter["hosp"]    = inter["Hospitalizations (estimated)"].apply(safe_float)
inter["injured"] = inter["Number of Injured Individuals"].apply(safe_float)

agg = inter.groupby("key").agg(
    crashes=("key", "count"),
    hospitalizations=("hosp", "sum"),
    injuries=("injured", "sum"),
    street1=("s1", "first"),
    street2=("s2", "first"),
).reset_index().sort_values("crashes", ascending=False)

agg = agg[agg["crashes"] >= 3].copy()

# ── Look up intersection coords from graph ─────────────────────────────────────
print("Resolving intersection coordinates...")
coords = [find_intersection(r["street1"], r["street2"]) for _, r in agg.iterrows()]
agg["coords"] = coords
matched = agg.dropna(subset=["coords"])
print(f"Resolved {len(matched)}/{len(agg)} intersections from road network")

# ── Build map ──────────────────────────────────────────────────────────────────
m = folium.Map(location=[42.3736, -71.1097], zoom_start=14, tiles="CartoDB positron")

heat_data = [[r["coords"][0], r["coords"][1], r["crashes"]] for _, r in matched.iterrows()]
HeatMap(heat_data, radius=20, blur=25, min_opacity=0.3, name="Heatmap").add_to(m)

markers = folium.FeatureGroup(name="Intersections", show=True)
max_n = matched["crashes"].max()

for _, row in matched.iterrows():
    lat, lon = row["coords"]
    n, hosp, inj = row["crashes"], int(row["hospitalizations"]), int(row["injuries"])
    radius = 5 + 22 * (n / max_n) ** 0.55

    if hosp >= 5:
        color, fill = "#7b241c", "#c0392b"   # dark red: severe
    elif hosp >= 2:
        color, fill = "#a04000", "#e67e22"   # orange: moderate
    elif hosp == 1:
        color, fill = "#9a7d0a", "#f1c40f"   # yellow: minor
    else:
        color, fill = "#0e6655", "#1abc9c"   # teal: no hospitalizations

    folium.CircleMarker(
        location=[lat, lon],
        radius=radius,
        color=color, weight=1.5,
        fill=True, fill_color=fill, fill_opacity=0.8,
        popup=folium.Popup(
            f"<b>{row['street1']} & {row['street2']}</b><br>"
            f"Crashes: <b>{n}</b> &nbsp;|&nbsp; Injuries: {inj} &nbsp;|&nbsp; Hosp: {hosp}",
            max_width=280),
        tooltip=f"{row['street1']} & {row['street2']} — {n} crashes",
    ).add_to(markers)

markers.add_to(m)
folium.LayerControl(collapsed=False).add_to(m)

m.get_root().html.add_child(folium.Element("""
<div style="position:fixed;bottom:30px;left:30px;z-index:1000;background:white;
     padding:14px 18px;border-radius:10px;border:1px solid #ccc;
     font-family:sans-serif;font-size:12px;box-shadow:2px 2px 8px rgba(0,0,0,.15);min-width:200px;">
  <b style="font-size:13px;">Cambridge Crash Intersections</b><br><br>
  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#c0392b;vertical-align:middle;margin-right:6px;"></span>≥5 hospitalizations<br><br>
  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#e67e22;vertical-align:middle;margin-right:6px;"></span>2–4 hospitalizations<br><br>
  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#f1c40f;vertical-align:middle;margin-right:6px;"></span>1 hospitalization<br><br>
  <span style="display:inline-block;width:12px;height:12px;border-radius:50%;background:#1abc9c;vertical-align:middle;margin-right:6px;"></span>No hospitalizations<br><br>
  <span style="font-size:11px;color:#888;">Circle size ∝ crash count &nbsp;|&nbsp; ≥3 crashes shown</span>
</div>
"""))

m.get_root().html.add_child(folium.Element("""
<div style="position:fixed;top:16px;left:50%;transform:translateX(-50%);z-index:1000;
     background:white;padding:10px 24px;border-radius:8px;border:1px solid #ddd;
     font-family:sans-serif;font-size:15px;font-weight:600;box-shadow:2px 2px 6px rgba(0,0,0,.12);">
  Cambridge CPD Crash Log — Street-Level Intensity
</div>
"""))

m.save("cambridge_crashes_map.html")
print("\nMap saved → cambridge_crashes_map.html")
print("\nTop 5 hotspots:")
for _, r in matched.head(5).iterrows():
    print(f"  {r['street1']} & {r['street2']}: {int(r['crashes'])} crashes")

from __future__ import annotations

import heapq
from collections import defaultdict
from datetime import date

import geopandas as gpd
import pandas as pd
from shapely import wkt

from common import (
    ANALYSIS_DATE,
    AREAS,
    CRS_METRIC,
    CRS_WEB,
    OUT,
    SGIS_KEYWORDS,
    allocated_sgis_for_geometry_all_available,
    aggregation_boundary_paths,
    ensure_dirs,
    load_boundary,
    sgis_csv_path,
    write_json,
)

EXCLUDED_FUTURE_LINES = ["GTX-B", "GTX-C", "신안산선", "위례신사선"]


def parse_date(value) -> date | None:
    text = "" if value is None else str(value).strip()
    if not text or text.lower() == "nan":
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def active_by_2023(value) -> bool:
    begin = parse_date(value)
    return begin is None or begin <= ANALYSIS_DATE


def load_active_network() -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    root = OUT.parents[1] / "subway_network" / "network"
    nodes = pd.read_csv(root / "nodes.tsv", sep="\t", dtype=str, encoding="utf-8", encoding_errors="ignore")
    links = pd.read_csv(root / "links.tsv", sep="\t", dtype=str, encoding="utf-8", encoding_errors="ignore")

    begin_col = "effective_begin" if "effective_begin" in nodes.columns else "begin"
    nodes = nodes[nodes[begin_col].map(active_by_2023) & nodes["begin"].map(active_by_2023)].copy()
    links = links[links["begin"].map(active_by_2023)].copy()
    for line in EXCLUDED_FUTURE_LINES:
        if "linenm" in nodes.columns:
            nodes = nodes[~nodes["linenm"].fillna("").str.contains(line, regex=False)]
        for col in ["linenm_from", "linenm_to"]:
            if col in links.columns:
                links = links[~links[col].fillna("").str.contains(line, regex=False)]

    active_ids = set(nodes["id"].astype(str))
    links = links[links["fromNode"].astype(str).isin(active_ids) & links["toNode"].astype(str).isin(active_ids)].copy()
    geometry = nodes["geometry_wkt"].map(wkt.loads)
    nodes_gdf = gpd.GeoDataFrame(nodes, geometry=geometry, crs="EPSG:5179").to_crs(CRS_METRIC)
    return nodes_gdf, links


def build_graph(links: pd.DataFrame) -> dict[str, list[tuple[str, float]]]:
    graph: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for _, row in links.iterrows():
        a = str(row["fromNode"])
        b = str(row["toNode"])
        try:
            ft = float(row["timeFT"])
            tf = float(row["timeTF"])
        except (TypeError, ValueError):
            continue
        graph[a].append((b, ft / 60.0))
        graph[b].append((a, tf / 60.0))
    return graph


def dijkstra(graph: dict[str, list[tuple[str, float]]], start: str, max_minutes: float = 60.0) -> dict[str, float]:
    dist = {start: 0.0}
    pq = [(0.0, start)]
    while pq:
        current, node = heapq.heappop(pq)
        if current > dist[node] or current > max_minutes:
            continue
        for nxt, cost in graph.get(node, []):
            nd = current + cost
            if nd <= max_minutes and nd < dist.get(nxt, float("inf")):
                dist[nxt] = nd
                heapq.heappush(pq, (nd, nxt))
    return dist


def station_catchment_geometry(nodes: gpd.GeoDataFrame, reachable_ids: set[str], walk_radius_m: float = 800.0):
    reached = nodes[nodes["id"].astype(str).isin(reachable_ids)]
    if reached.empty:
        return None
    return reached.geometry.buffer(walk_radius_m).union_all()


def build_accessibility() -> list[dict]:
    ensure_dirs()
    nodes, links = load_active_network()
    graph = build_graph(links)
    validation_rows = []
    results = []

    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        geom = boundary.geometry.iloc[0]
        centroid = geom.centroid
        nodes = nodes.copy()
        nodes["origin_distance_m"] = nodes.geometry.distance(centroid)
        origin = nodes.sort_values("origin_distance_m").iloc[0]
        origin_id = str(origin["id"])
        travel_times = dijkstra(graph, origin_id, 60.0)

        cumulative = []
        for minutes in [15, 30, 45, 60]:
            reachable_ids = {node_id for node_id, t in travel_times.items() if t <= minutes}
            reached = nodes[nodes["id"].astype(str).isin(reachable_ids)].copy()
            reached["travel_time_min"] = reached["id"].astype(str).map(travel_times)
            reached.to_crs(CRS_WEB).to_file(OUT / "transport" / f"{key}_rail_{minutes}.geojson", driver="GeoJSON")

            catchment_geom = station_catchment_geometry(nodes, reachable_ids)
            if catchment_geom is None:
                pop = households = workers = businesses = 0.0
                meta = {"features": 0}
            else:
                pop, pop_meta = allocated_sgis_for_geometry_all_available(catchment_geom, SGIS_KEYWORDS["population"])
                households, household_meta = allocated_sgis_for_geometry_all_available(catchment_geom, SGIS_KEYWORDS["households"])
                workers, worker_meta = allocated_sgis_for_geometry_all_available(catchment_geom, SGIS_KEYWORDS["workers"])
                businesses, business_meta = allocated_sgis_for_geometry_all_available(catchment_geom, SGIS_KEYWORDS["businesses_total"])
                if not businesses:
                    businesses, business_meta = allocated_sgis_for_geometry_all_available(catchment_geom, SGIS_KEYWORDS["businesses"])
                meta = {"population": pop_meta, "households": household_meta, "workers": worker_meta, "businesses": business_meta}

                iso = gpd.GeoDataFrame(
                    [{"area_key": key, "minutes": minutes, "source": "2023 rail network dijkstra + 800m station catchment"}],
                    geometry=[catchment_geom],
                    crs=CRS_METRIC,
                )
                if minutes in [30, 60]:
                    iso.to_crs(CRS_WEB).to_file(OUT / "transport" / f"{key}_isochrone_{minutes}.geojson", driver="GeoJSON")

            cumulative.append(
                {
                    "minutes": minutes,
                    "reachable_station_count": int(len(reached)),
                    "allocated_population": round(pop, 1),
                    "allocated_households": round(households, 1),
                    "allocated_workers": round(workers, 1),
                    "allocated_businesses": round(businesses, 1),
                    "allocation_meta": meta,
                }
            )

        nearest_m = float(origin["origin_distance_m"])
        validation_rows.append(
            {
                "area_key": key,
                "origin_station_id": origin_id,
                "origin_station_name": origin.get("statnm"),
                "origin_line": origin.get("linenm"),
                "origin_distance_m": round(nearest_m, 1),
                "active_node_count": int(len(nodes)),
                "active_link_count": int(len(links)),
                "reachable_30_count": next(r["reachable_station_count"] for r in cumulative if r["minutes"] == 30),
                "reachable_60_count": next(r["reachable_station_count"] for r in cumulative if r["minutes"] == 60),
                "aggregation_boundary_regions": sorted(aggregation_boundary_paths().keys()),
                "missing_sgis_value_regions": {
                    code: {
                        name: sgis_csv_path(code, keyword) is None
                        for name, keyword in SGIS_KEYWORDS.items()
                    }
                    for code in sorted(aggregation_boundary_paths().keys())
                },
            }
        )

        reached_60 = nodes[nodes["id"].astype(str).isin(set(travel_times))].copy()
        reached_60["travel_time_min"] = reached_60["id"].astype(str).map(travel_times)
        reached_60.to_crs(CRS_WEB).to_file(OUT / "transport" / f"{key}_rail_2023.geojson", driver="GeoJSON")

        results.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "analysis_date": ANALYSIS_DATE.isoformat(),
                "origin_station_id": origin_id,
                "origin_station_name": origin.get("statnm"),
                "nearest_station_m": round(nearest_m, 1),
                "station_count_2km": int((nodes["origin_distance_m"] <= 2000).sum()),
                "commuter_catchment_minutes": 60,
                "cumulative_accessibility": cumulative,
                "excluded_future_lines": EXCLUDED_FUTURE_LINES,
                "method": "2023 rail network dijkstra; reachable station 800m catchment; SGIS aggregation area-weighted allocation",
            }
        )

    write_json(OUT / "analytics" / "accessibility.json", results)
    write_json(OUT / "reports" / "accessibility_validation_report.json", validation_rows)
    return results


def main() -> None:
    for row in build_accessibility():
        count60 = next(x["reachable_station_count"] for x in row["cumulative_accessibility"] if x["minutes"] == 60)
        print(f"{row['area_key']}: origin={row['origin_station_name']} reachable_60={count60}")


if __name__ == "__main__":
    main()

from __future__ import annotations

from datetime import date

import geopandas as gpd
import pandas as pd
from shapely import wkt

from common import ANALYSIS_DATE, AREAS, CRS_METRIC, CRS_WEB, OUT, allocated_sgis_for_geometry, ensure_dirs, load_boundary, write_json


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


def load_active_nodes() -> gpd.GeoDataFrame:
    path = OUT.parents[1] / "subway_network" / "network" / "nodes.tsv"
    nodes = pd.read_csv(path, sep="\t", dtype=str, encoding="utf-8", encoding_errors="ignore")
    begin_col = "effective_begin" if "effective_begin" in nodes.columns else "begin"
    nodes = nodes[nodes[begin_col].map(active_by_2023) & nodes["begin"].map(active_by_2023)].copy()
    for line in EXCLUDED_FUTURE_LINES:
        if "linenm" in nodes.columns:
            nodes = nodes[~nodes["linenm"].fillna("").str.contains(line, regex=False)]
    geometry = nodes["geometry_wkt"].map(wkt.loads)
    return gpd.GeoDataFrame(nodes, geometry=geometry, crs="EPSG:5179").to_crs(CRS_METRIC)


def build_accessibility() -> list[dict]:
    ensure_dirs()
    nodes = load_active_nodes()
    results = []
    for key, cfg in AREAS.items():
        boundary = load_boundary(key)
        geom = boundary.geometry.iloc[0]
        centroid = geom.centroid
        nearby = nodes[nodes.geometry.distance(centroid) <= 20000].copy()
        if nearby.empty:
            nearest_m = None
            station_count_2km = 0
        else:
            nearby["distance_m"] = nearby.geometry.distance(centroid)
            nearest_m = float(nearby["distance_m"].min())
            station_count_2km = int((nearby["distance_m"] <= 2000).sum())
        nearby.to_crs(CRS_WEB).to_file(OUT / "transport" / f"{key}_rail_2023.geojson", driver="GeoJSON")

        for minutes, radius_m in [(30, 6000), (60, 12000)]:
            iso = gpd.GeoDataFrame(
                [{"area_key": key, "minutes": minutes, "source": "sample_buffer_when_network_times_missing"}],
                geometry=[centroid.buffer(radius_m)],
                crs=CRS_METRIC,
            )
            iso.to_crs(CRS_WEB).to_file(OUT / "transport" / f"{key}_isochrone_{minutes}.geojson", driver="GeoJSON")

        cumulative = []
        for minutes in [15, 30, 45, 60]:
            radius_km = minutes * 0.2
            catchment_geom = centroid.buffer(radius_km * 1000)
            pop, pop_meta = allocated_sgis_for_geometry(key, catchment_geom, "인구총괄(총인구)")
            households, _household_meta = allocated_sgis_for_geometry(key, catchment_geom, "가구총괄")
            workers, worker_meta = allocated_sgis_for_geometry(key, catchment_geom, "산업분류별(10차_대분류)_종사자수")
            businesses, _business_meta = allocated_sgis_for_geometry(key, catchment_geom, "산업분류별(10차_대분류)_총괄사업체수")
            if not businesses:
                businesses, _business_meta = allocated_sgis_for_geometry(key, catchment_geom, "산업분류별(10차_대분류)_사업체수")
            cumulative.append(
                {
                    "minutes": minutes,
                    "radius_km": round(radius_km, 1),
                    "allocated_population": round(pop, 1),
                    "allocated_households": round(households, 1),
                    "allocated_workers": round(workers, 1),
                    "allocated_businesses": round(businesses, 1),
                    "allocation_meta": {"population": pop_meta, "workers": worker_meta},
                }
            )

        results.append(
            {
                "area_key": key,
                "label": cfg["label"],
                "analysis_date": ANALYSIS_DATE.isoformat(),
                "active_station_count_20km": int(len(nearby)),
                "station_count_2km": station_count_2km,
                "nearest_station_m": round(nearest_m, 1) if nearest_m is not None else None,
                "isochrone_30_area_km2": round(3.14159 * 6 * 6, 2),
                "isochrone_60_area_km2": round(3.14159 * 12 * 12, 2),
                "commuter_catchment_minutes": 60,
                "cumulative_accessibility": cumulative,
                "excluded_future_lines": EXCLUDED_FUTURE_LINES,
                "method": "same-time buffer with aggregation-area-weighted allocation",
            }
        )
    write_json(OUT / "analytics" / "accessibility.json", results)
    return results


def main() -> None:
    for row in build_accessibility():
        print(f"{row['area_key']}: nearest_station_m={row['nearest_station_m']} station_count_2km={row['station_count_2km']}")


if __name__ == "__main__":
    main()
